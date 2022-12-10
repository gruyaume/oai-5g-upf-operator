#!/usr/bin/env python3
# Copyright 2022 Guillaume Belanger
# See LICENSE file for licensing details.

"""Charmed Operator for the OpenAirInterface 5G Core UPF component."""


import logging

from charms.oai_5g_nrf.v0.fiveg_nrf import FiveGNRFRequires  # type: ignore[import]
from charms.observability_libs.v1.kubernetes_service_patch import (  # type: ignore[import]
    KubernetesServicePatch,
    ServicePort,
)
from jinja2 import Environment, FileSystemLoader
from ops.charm import CharmBase, ConfigChangedEvent, InstallEvent
from ops.main import main
from ops.model import ActiveStatus, BlockedStatus, WaitingStatus

from kubernetes import Kubernetes

logger = logging.getLogger(__name__)

BASE_CONFIG_PATH = "/openair-spgwu-tiny/etc"
CONFIG_FILE_NAME = "spgw_u.conf"


class Oai5GUPFOperatorCharm(CharmBase):
    """Charm the service."""

    def __init__(self, *args):
        """Observes juju events."""
        super().__init__(*args)
        self._container_name = "upf"
        self._container = self.unit.get_container(self._container_name)
        self.kubernetes = Kubernetes(namespace=self.model.name)
        self.service_patcher = KubernetesServicePatch(
            charm=self,
            ports=[
                ServicePort(
                    name="oai-spgwu-tiny",
                    port=8805,
                    protocol="UDP",
                    targetPort=8805,
                ),
                ServicePort(
                    name="s1u",
                    port=2152,
                    protocol="UDP",
                    targetPort=2152,
                ),
            ],
        )
        self.nrf_requires = FiveGNRFRequires(self, "fiveg-nrf")
        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.fiveg_nrf_relation_changed, self._on_config_changed)

    def _on_install(self, event: InstallEvent) -> None:
        """Triggered on install event.

        Args:
            event: Juju event

        Returns:
            None
        """
        if not self.kubernetes.statefulset_is_patched(
            statefulset_name=self.app.name,
        ):
            self.kubernetes.patch_statefulset(
                statefulset_name=self.app.name,
            )

    def _on_config_changed(self, event: ConfigChangedEvent) -> None:
        """Triggered on any change in configuration.

        Args:
            event: Config Changed Event

        Returns:
            None
        """
        if not self._container.can_connect():
            self.unit.status = WaitingStatus("Waiting for Pebble in workload container")
            event.defer()
            return
        if not self._nrf_relation_created:
            self.unit.status = BlockedStatus("Waiting for relation to NRF to be created")
            return
        if not self.nrf_requires.nrf_ipv4_address_available:
            self.unit.status = WaitingStatus(
                "Waiting for NRF IPv4 address to be available in relation data"
            )
            return

        self._push_config()
        self._update_pebble_layer()
        self.unit.status = ActiveStatus()

    def _update_pebble_layer(self) -> None:
        """Updates pebble layer with new configuration.

        Returns:
            None
        """
        self._container.add_layer("upf", self._pebble_layer, combine=True)
        self._container.replan()
        self.unit.status = ActiveStatus()

    @property
    def _nrf_relation_created(self) -> bool:
        return self._relation_created("fiveg-nrf")

    def _relation_created(self, relation_name: str) -> bool:
        if not self.model.get_relation(relation_name):
            return False
        return True

    def _push_config(self) -> None:
        jinja2_environment = Environment(loader=FileSystemLoader("src/templates/"))
        template = jinja2_environment.get_template(f"{CONFIG_FILE_NAME}.j2")
        content = template.render(
            spgw_fqdn=self._config_spgw_fqdn,
            instance=self._config_instance,
            pid_directory=self._config_pid_directory,
            sgw_s1u_interface=self._config_sgw_s1u_interface,
            thread_s1u_priority=self._config_thread_s1u_priority,
            sgw_sx_interface=self._config_sgw_sx_interface,
            thread_sx_priority=self._config_thread_sx_priority,
            pgw_sgi_interface=self._config_pgw_sgi_interface,
            thread_sgi_priority=self._config_thread_sgi_priority,
            network_ue_ip=self._config_network_ue_ip,
            spgw_c0_ip_address=self._config_spgw_c0_ip_address,
            bypass_ul_pfcp_rules=self._config_bypass_ul_pfcp_rules,
            enable_5g_features=self._config_enable_5g_features,
            register_nrf=self._config_register_nrf,
            use_fqdn_nrf=self._config_use_fqdn_nrf,
            upf_fqdn_5g=self._config_upf_fqdn_5g,
            nrf_ipv4_address=self.nrf_requires.nrf_ipv4_address,
            nrf_port=self.nrf_requires.nrf_port,
            nrf_api_version=self.nrf_requires.nrf_api_version,
            nrf_fqdn=self.nrf_requires.nrf_fqdn,
            nssai_sst_0=self._config_nssai_sst_0,
            nssai_sd_0=self._config_nssai_sd_0,
            dnn_0=self._config_dnn_0,
            nssai_sst_1=self._config_nssai_sst_1,
            nssai_sd_1=self._config_nssai_sd_1,
            dnn_1=self._config_dnn_1,
            nssai_sst_2=self._config_nssai_sst_2,
            nssai_sd_2=self._config_nssai_sd_2,
            dnn_2=self._config_dnn_2,
            nssai_sst_3=self._config_nssai_sst_3,
            nssai_sd_3=self._config_nssai_sd_3,
            dnn_3=self._config_dnn_3,
        )

        self._container.push(path=f"{BASE_CONFIG_PATH}/{CONFIG_FILE_NAME}", source=content)
        logger.info(f"Wrote file to container: {CONFIG_FILE_NAME}")

    @property
    def _config_file_is_pushed(self) -> bool:
        """Check if config file is pushed to the container."""
        if not self._container.exists(f"{BASE_CONFIG_PATH}/{CONFIG_FILE_NAME}"):
            logger.info(f"Config file is not written: {CONFIG_FILE_NAME}")
            return False
        logger.info("Config file is pushed")
        return True

    @property
    def _config_spgw_fqdn(self) -> str:
        return f"gw{self._config_gw_id}.spgw.node.epc.mnc{self._config_mnc}.mcc{self._config_mcc}.{self._config_realm}"  # noqa: E501

    @property
    def _config_gw_id(self) -> str:
        return self.model.config["gw-id"]

    @property
    def _config_mnc(self) -> str:
        return self.model.config["mnc"]

    @property
    def _config_mcc(self) -> str:
        return self.model.config["mcc"]

    @property
    def _config_realm(self) -> str:
        return self.model.config["realm"]

    @property
    def _config_instance(self) -> str:
        return "0"

    @property
    def _config_pid_directory(self) -> str:
        return "/var/run"

    @property
    def _config_sgw_s1u_interface(self) -> str:
        return self.model.config["sgw-s1u-interface"]

    @property
    def _config_thread_s1u_priority(self) -> str:
        return self.model.config["thread-s1u-priority"]

    @property
    def _config_sgw_sx_interface(self) -> str:
        return self.model.config["sgw-sx-interface"]

    @property
    def _config_thread_sx_priority(self) -> str:
        return self.model.config["thread-sx-priority"]

    @property
    def _config_pgw_sgi_interface(self) -> str:
        return self.model.config["pgw-sgi-interface"]

    @property
    def _config_thread_sgi_priority(self) -> str:
        return self.model.config["thread-sgi-priority"]

    @property
    def _config_network_ue_ip(self) -> str:
        return self.model.config["network-ue-ip"]

    @property
    def _config_spgw_c0_ip_address(self) -> str:
        return "127.0.0.1"

    @property
    def _config_bypass_ul_pfcp_rules(self) -> str:
        return "no"

    @property
    def _config_enable_5g_features(self) -> str:
        return "yes"

    @property
    def _config_register_nrf(self) -> str:
        return "yes"

    @property
    def _config_use_fqdn_nrf(self) -> str:
        return "yes"

    @property
    def _config_upf_fqdn_5g(self) -> str:
        return f"{self.model.app.name}.{self.model.name}.svc.cluster.local"

    @property
    def _config_nssai_sst_0(self) -> str:
        return "1"

    @property
    def _config_nssai_sd_0(self) -> str:
        return "1"

    @property
    def _config_dnn_0(self) -> str:
        return "oai"

    @property
    def _config_nssai_sst_1(self) -> str:
        return "1"

    @property
    def _config_nssai_sd_1(self) -> str:
        return "1"

    @property
    def _config_dnn_1(self) -> str:
        return "oai"

    @property
    def _config_nssai_sst_2(self) -> str:
        return "1"

    @property
    def _config_nssai_sd_2(self) -> str:
        return "1"

    @property
    def _config_dnn_2(self) -> str:
        return "oai"

    @property
    def _config_nssai_sst_3(self) -> str:
        return "1"

    @property
    def _config_nssai_sd_3(self) -> str:
        return "1"

    @property
    def _config_dnn_3(self) -> str:
        return "oai"

    @property
    def _pebble_layer(self) -> dict:
        """Return a dictionary representing a Pebble layer."""
        return {
            "summary": "upf layer",
            "description": "pebble config layer for upf",
            "services": {
                "upf": {
                    "override": "replace",
                    "summary": "upf",
                    "command": f"/openair-spgwu-tiny/bin/oai_spgwu -c {BASE_CONFIG_PATH}/{CONFIG_FILE_NAME} -o",  # noqa: E501
                    "startup": "enabled",
                }
            },
        }


if __name__ == "__main__":
    main(Oai5GUPFOperatorCharm)
