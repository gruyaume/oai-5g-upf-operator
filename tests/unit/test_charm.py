# Copyright 2022 Guillaume Belanger
# See LICENSE file for licensing details.

import unittest
from unittest.mock import patch

import ops.testing
from lightkube.models.apps_v1 import StatefulSet, StatefulSetSpec
from lightkube.models.core_v1 import (
    Container,
    PodSecurityContext,
    PodSpec,
    PodTemplateSpec,
    SecurityContext,
)
from lightkube.models.meta_v1 import LabelSelector
from lightkube.resources.apps_v1 import StatefulSet as StatefulSetResource
from lightkube.types import PatchType
from ops.model import ActiveStatus
from ops.testing import Harness

from charm import Oai5GUPFOperatorCharm


class TestCharm(unittest.TestCase):
    @patch("lightkube.core.client.GenericSyncClient")
    @patch(
        "charm.KubernetesServicePatch",
        lambda charm, ports: None,
    )
    def setUp(self, patch_lightkube):
        ops.testing.SIMULATE_CAN_CONNECT = True
        self.namespace = "whatever"
        self.addCleanup(setattr, ops.testing, "SIMULATE_CAN_CONNECT", False)
        self.harness = Harness(Oai5GUPFOperatorCharm)
        self.addCleanup(self.harness.cleanup)
        self.harness.set_model_name(name=self.namespace)
        self.harness.begin()

    def _create_nrf_relation_with_valid_data(self):
        relation_id = self.harness.add_relation("fiveg-nrf", "nrf")
        self.harness.add_relation_unit(relation_id=relation_id, remote_unit_name="nrf/0")

        nrf_ipv4_address = "1.2.3.4"
        nrf_port = "81"
        nrf_api_version = "v1"
        nrf_fqdn = "nrf.example.com"
        key_values = {
            "nrf_ipv4_address": nrf_ipv4_address,
            "nrf_port": nrf_port,
            "nrf_fqdn": nrf_fqdn,
            "nrf_api_version": nrf_api_version,
        }
        self.harness.update_relation_data(
            relation_id=relation_id, app_or_unit="nrf", key_values=key_values
        )
        return nrf_ipv4_address, nrf_port, nrf_api_version, nrf_fqdn

    @patch("lightkube.Client.patch")
    @patch("lightkube.Client.get")
    def test_given_statefulset_not_yet_patched_when_on_install_then_statefulset_is_patched(
        self, patch_k8s_get, patch_k8s_patch
    ):
        patch_k8s_get.return_value = StatefulSet(
            spec=StatefulSetSpec(
                template=PodTemplateSpec(
                    spec=PodSpec(
                        containers=[
                            Container(
                                name="charm",
                            ),
                            Container(name="workload", securityContext=SecurityContext()),
                        ],
                        securityContext=PodSecurityContext(),
                    )
                ),
                serviceName="upf",
                selector=LabelSelector(),
            )
        )
        self.harness.charm.on.install.emit()

        args, kwargs = patch_k8s_patch.call_args

        self.assertEqual(kwargs["name"], "oai-5g-upf")
        self.assertEqual(kwargs["namespace"], self.namespace)
        self.assertEqual(kwargs["res"], StatefulSetResource)
        self.assertEqual(kwargs["patch_type"], PatchType.MERGE)
        self.assertEqual(kwargs["obj"].spec.template.spec.securityContext.runAsUser, 0)
        self.assertEqual(kwargs["obj"].spec.template.spec.securityContext.runAsGroup, 0)
        self.assertEqual(
            kwargs["obj"].spec.template.spec.containers[1].securityContext.privileged, True
        )

    @patch("ops.model.Container.push")
    def test_given_nrf_relation_contains_nrf_info_when_nrf_relation_joined_then_config_file_is_pushed(  # noqa: E501
        self, mock_push
    ):
        self.harness.set_can_connect(container="upf", val=True)
        (
            nrf_ipv4_address,
            nrf_port,
            nrf_api_version,
            nrf_fqdn,
        ) = self._create_nrf_relation_with_valid_data()

        mock_push.assert_called_with(
            path="/openair-spgwu-tiny/etc/spgw_u.conf",
            source="################################################################################\n"  # noqa: E501, W505
            "# Licensed to the OpenAirInterface (OAI) Software Alliance under one or more\n"
            "# contributor license agreements.  See the NOTICE file distributed with\n"
            "# this work for additional information regarding copyright ownership.\n"
            "# The OpenAirInterface Software Alliance licenses this file to You under\n"
            '# the OAI Public License, Version 1.1  (the "License"); you may not use this file\n'  # noqa: E501, W505
            "# except in compliance with the License.\n"
            "# You may obtain a copy of the License at\n"
            "#\n#      http://www.openairinterface.org/?page_id=698\n"
            "#\n"
            "# Unless required by applicable law or agreed to in writing, software\n"
            '# distributed under the License is distributed on an "AS IS" BASIS,\n'
            "# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.\n"
            "# See the License for the specific language governing permissions and\n"
            "# limitations under the License.\n"
            "#-------------------------------------------------------------------------------\n"  # noqa: E501, W505
            "# For more information about the OpenAirInterface (OAI) Software Alliance:\n"
            "#      contact@openairinterface.org\n################################################################################\n"  # noqa: E501, W505
            "SPGW-U =\n"
            "{\n"
            '    FQDN = "gw1.spgw.node.epc.mnc99.mcc208.3gpp.org"; # FQDN for 4G\n'
            "    INSTANCE                       = 0;            # 0 is the default\n"
            '    PID_DIRECTORY                  = "/var/run";     # /var/run is the default\n\n'  # noqa: E501, W505
            "    #ITTI_TASKS :\n"
            "    #{\n"
            "        #ITTI_TIMER_SCHED_PARAMS :\n"
            "        #{\n"
            "            #CPU_ID       = 1;\n"
            '            #SCHED_POLICY = "SCHED_FIFO"; # Values in { SCHED_OTHER, SCHED_IDLE, SCHED_BATCH, SCHED_FIFO, SCHED_RR }\n'  # noqa: E501, W505
            "            #SCHED_PRIORITY = 85;\n"
            "        #};\n"
            "        #S1U_SCHED_PARAMS :\n"
            "        #{\n"
            "            #CPU_ID       = 1;\n"
            '            #SCHED_POLICY = "SCHED_FIFO"; # Values in { SCHED_OTHER, SCHED_IDLE, SCHED_BATCH, SCHED_FIFO, SCHED_RR }\n'  # noqa: E501, W505
            "            #SCHED_PRIORITY = 84;\n"
            "        #};\n"
            "        #SX_SCHED_PARAMS :\n"
            "        #{\n"
            "            #CPU_ID       = 1;\n"
            '            #SCHED_POLICY = "SCHED_FIFO"; # Values in { SCHED_OTHER, SCHED_IDLE, SCHED_BATCH, SCHED_FIFO, SCHED_RR }\n'  # noqa: E501, W505
            "            #SCHED_PRIORITY = 84;\n"
            "        #};\n"
            "        #ASYNC_CMD_SCHED_PARAMS :\n"
            "        #{\n"
            "            #CPU_ID       = 1;\n"
            '            #SCHED_POLICY = "SCHED_FIFO"; # Values in { SCHED_OTHER, SCHED_IDLE, SCHED_BATCH, SCHED_FIFO, SCHED_RR }\n'  # noqa: E501, W505
            "            #SCHED_PRIORITY = 84;\n"
            "        #};\n"
            "    #};\n\n"
            "    INTERFACES :\n"
            "    {\n"
            "        S1U_S12_S4_UP :\n"
            "        {\n"
            "            # S-GW binded interface for S1-U communication (GTPV1-U) can be ethernet interface, virtual ethernet interface, we don't advise wireless interfaces\n"  # noqa: E501, W505
            '            INTERFACE_NAME         = "eth0";  # STRING, interface name, YOUR NETWORK CONFIG HERE\n'  # noqa: E501, W505
            '            IPV4_ADDRESS           = "read";                                    # STRING, CIDR or "read to let app read interface configured IP address\n'  # noqa: E501, W505
            "            #PORT                   = 2152;                                     # Default is 2152\n"  # noqa: E501, W505
            "            SCHED_PARAMS :\n"
            "            {\n"
            "                #CPU_ID       = 2;\n"
            '                SCHED_POLICY = "SCHED_FIFO"; # Values in { SCHED_OTHER, SCHED_IDLE, SCHED_BATCH, SCHED_FIFO, SCHED_RR }\n'  # noqa: E501, W505
            "                SCHED_PRIORITY = 88;\n"
            "                POOL_SIZE = 1; # NUM THREADS\n"
            "            };\n"
            "        };\n"
            "        SX :\n"
            "        {\n"
            "            # S/P-GW binded interface for SX communication\n"
            '            INTERFACE_NAME         = "eth0"; # STRING, interface name\n'
            '            IPV4_ADDRESS           = "read";                        # STRING, CIDR or "read" to let app read interface configured IP address\n'  # noqa: E501, W505
            "            #PORT                   = 8805;                         # Default is 8805\n"  # noqa: E501, W505
            "            SCHED_PARAMS :\n"
            "            {\n"
            "                #CPU_ID       = 1;\n"
            '                SCHED_POLICY = "SCHED_FIFO"; # Values in { SCHED_OTHER, SCHED_IDLE, SCHED_BATCH, SCHED_FIFO, SCHED_RR }\n'  # noqa: E501, W505
            "                SCHED_PRIORITY = 88;\n                POOL_SIZE = 1; # NUM THREADS\n"  # noqa: E501, W505
            "            };\n"
            "        };\n"
            "        SGI :\n"
            "        {\n"
            "           # No config to set, the software will set the SGi interface to the interface used for the default route.\n"  # noqa: E501, W505
            '            INTERFACE_NAME         = "eth0"; # STRING, interface name or "default_gateway"\n'  # noqa: E501, W505
            '            IPV4_ADDRESS           = "read";                         # STRING, CIDR or "read" to let app read interface configured IP address\n'  # noqa: E501, W505
            "            SCHED_PARAMS :\n"
            "            {\n"
            "                #CPU_ID       = 3;\n"
            '                SCHED_POLICY = "SCHED_FIFO"; # Values in { SCHED_OTHER, SCHED_IDLE, SCHED_BATCH, SCHED_FIFO, SCHED_RR }\n'  # noqa: E501, W505
            "                SCHED_PRIORITY = 98;\n"
            "                POOL_SIZE = 1; # NUM THREADS\n"
            "            };\n"
            "        };\n"
            "    };\n\n"
            '    SNAT = "yes"; # SNAT Values in {yes, no}\n'
            "    PDN_NETWORK_LIST  = (\n"
            '                      {NETWORK_IPV4 = "12.1.1.0/24";} # 1 ITEM SUPPORTED ONLY\n'  # noqa: E501, W505
            "                    );\n\n"
            "    SPGW-C_LIST = (\n"
            '         {IPV4_ADDRESS="127.0.0.1" ;}\n'
            "    );\n\n"
            "    NON_STANDART_FEATURES :\n"
            "    {\n"
            "        BYPASS_UL_PFCP_RULES = \"no\"; # 'no' for standard features, yes for enhancing UL throughput\n"  # noqa: E501, W505
            "    };\n\n"
            "    SUPPORT_5G_FEATURES:\n"
            "    {\n"
            '       # STRING, {"yes", "no"},\n'
            "       ENABLE_5G_FEATURES = \"yes\" # Set to 'yes' to support 5G Features\n"
            "       REGISTER_NRF = \"yes\";            # Set to 'yes' if UPF resgisters to an NRF\n"  # noqa: E501, W505
            "       USE_FQDN_NRF = \"yes\";            # Set to 'yes' if UPF relies on a DNS/FQDN service to resolve NRF's FQDN\n"  # noqa: E501, W505
            f'       UPF_FQDN_5G  = "oai-5g-upf.{self.namespace}.svc.cluster.local";             # Set FQDN of UPF\n\n'  # noqa: E501, W505
            "       NRF :\n"
            "       {\n"
            f'          IPV4_ADDRESS = "{ nrf_ipv4_address }";  # YOUR NRF CONFIG HERE\n'
            f"          PORT         = {nrf_port};            # YOUR NRF CONFIG HERE (default: 80)\n"  # noqa: E501, W505
            "          HTTP_VERSION = 1;        #Set HTTP version for NRF (1 or 2)Default 1\n"  # noqa: E501, W505
            f'          API_VERSION  = "{nrf_api_version}";   # YOUR NRF API VERSION HERE\n'
            f'          FQDN = "{ nrf_fqdn }";\n'
            "       };\n\n"
            "       # Additional info to be sent to NRF for supporting Network Slicing\n"
            "       UPF_INFO = (\n"
            '          { NSSAI_SST = 1; NSSAI_SD = "1";  DNN_LIST = ({DNN = "oai";}); },\n'
            '          { NSSAI_SST = 1; NSSAI_SD = "1";  DNN_LIST = ({DNN = "oai";}); },\n'
            '          { NSSAI_SST = 1; NSSAI_SD = "1";  DNN_LIST = ({DNN = "oai";}); },\n'
            '          { NSSAI_SST = 1; NSSAI_SD = "1";  DNN_LIST = ({DNN = "oai";}); }\n'
            "       );\n"
            "    }\n"
            "};",
        )

    @patch("ops.model.Container.push")
    def test_given_nrf_and_db_relation_are_set_when_config_changed_then_pebble_plan_is_created(  # noqa: E501
        self, _
    ):
        self.harness.set_can_connect(container="upf", val=True)
        self._create_nrf_relation_with_valid_data()

        expected_plan = {
            "services": {
                "upf": {
                    "override": "replace",
                    "summary": "upf",
                    "command": "/openair-spgwu-tiny/bin/oai_spgwu -c /openair-spgwu-tiny/etc/spgw_u.conf -o",  # noqa: E501
                    "startup": "enabled",
                }
            },
        }
        self.harness.container_pebble_ready("upf")
        updated_plan = self.harness.get_container_pebble_plan("upf").to_dict()
        self.assertEqual(expected_plan, updated_plan)
        service = self.harness.model.unit.get_container("upf").get_service("upf")
        self.assertTrue(service.is_running())
        self.assertEqual(self.harness.model.unit.status, ActiveStatus())

    def test_given_unit_is_leader_when_upf_relation_joined_then_upf_relation_data_is_set(self):
        self.harness.set_leader(True)

        relation_id = self.harness.add_relation(relation_name="fiveg-upf", remote_app="upf")
        self.harness.add_relation_unit(relation_id=relation_id, remote_unit_name="upf/0")

        relation_data = self.harness.get_relation_data(
            relation_id=relation_id, app_or_unit=self.harness.model.app.name
        )

        assert relation_data["upf_ipv4_address"] == "127.0.0.1"
        assert relation_data["upf_fqdn"] == f"oai-5g-upf.{self.namespace}.svc.cluster.local"
