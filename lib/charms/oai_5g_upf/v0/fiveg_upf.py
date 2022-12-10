# Copyright 2022 Guillaume Belanger
# See LICENSE file for licensing details.

"""Interface used by provider and requirer of the 5G UPF."""

import logging
from typing import Optional

from ops.charm import CharmBase, CharmEvents, RelationChangedEvent
from ops.framework import EventBase, EventSource, Handle, Object

# The unique Charmhub library identifier, never change it
LIBID = "ed9606f2aaa64099937b7f57add2c42d"

# Increment this major API version when introducing breaking changes
LIBAPI = 0

# Increment this PATCH version before using `charmcraft publish-lib` or reset
# to 0 if you are raising the major API version
LIBPATCH = 2


logger = logging.getLogger(__name__)


class UPFAvailableEvent(EventBase):
    """Charm event emitted when an UPF is available."""

    def __init__(
        self,
        handle: Handle,
        upf_ipv4_address: str,
        upf_fqdn: str,
    ):
        """Init."""
        super().__init__(handle)
        self.upf_ipv4_address = upf_ipv4_address
        self.upf_fqdn = upf_fqdn

    def snapshot(self) -> dict:
        """Returns snapshot."""
        return {
            "upf_ipv4_address": self.upf_ipv4_address,
            "upf_fqdn": self.upf_fqdn,
        }

    def restore(self, snapshot: dict) -> None:
        """Restores snapshot."""
        self.upf_ipv4_address = snapshot["upf_ipv4_address"]
        self.upf_fqdn = snapshot["upf_fqdn"]


class FiveGUPFRequirerCharmEvents(CharmEvents):
    """List of events that the 5G UPF requirer charm can leverage."""

    upf_available = EventSource(UPFAvailableEvent)


class FiveGUPFRequires(Object):
    """Class to be instantiated by the charm requiring the 5G UPF Interface."""

    on = FiveGUPFRequirerCharmEvents()

    def __init__(self, charm: CharmBase, relationship_name: str):
        """Init."""
        super().__init__(charm, relationship_name)
        self.charm = charm
        self.relationship_name = relationship_name
        self.framework.observe(
            charm.on[relationship_name].relation_changed, self._on_relation_changed
        )

    def _on_relation_changed(self, event: RelationChangedEvent) -> None:
        """Handler triggered on relation changed event.

        Args:
            event: Juju event (RelationChangedEvent)

        Returns:
            None
        """
        relation = event.relation
        if not relation.app:
            logger.warning("No remote application in relation: %s", self.relationship_name)
            return
        remote_app_relation_data = relation.data[relation.app]
        if "upf_ipv4_address" not in remote_app_relation_data:
            logger.info(
                "No upf_ipv4_address in relation data - Not triggering upf_available event"
            )
            return
        if "upf_fqdn" not in remote_app_relation_data:
            logger.info("No upf_fqdn in relation data - Not triggering upf_available event")
            return
        self.on.upf_available.emit(
            upf_ipv4_address=remote_app_relation_data["upf_ipv4_address"],
            upf_fqdn=remote_app_relation_data["upf_fqdn"],
        )

    @property
    def upf_ipv4_address_available(self) -> bool:
        """Returns whether upf address is available in relation data."""
        if self.upf_ipv4_address:
            return True
        else:
            return False

    @property
    def upf_ipv4_address(self) -> Optional[str]:
        """Returns upf_ipv4_address from relation data."""
        relation = self.model.get_relation(relation_name=self.relationship_name)
        remote_app_relation_data = relation.data.get(relation.app)
        if not remote_app_relation_data:
            return None
        return remote_app_relation_data.get("upf_ipv4_address", None)

    @property
    def upf_fqdn_available(self) -> bool:
        """Returns whether upf fqdn is available in relation data."""
        if self.upf_fqdn:
            return True
        else:
            return False

    @property
    def upf_fqdn(self) -> Optional[str]:
        """Returns upf_fqdn from relation data."""
        relation = self.model.get_relation(relation_name=self.relationship_name)
        remote_app_relation_data = relation.data.get(relation.app)
        if not remote_app_relation_data:
            return None
        return remote_app_relation_data.get("upf_fqdn", None)


class FiveGUPFProvides(Object):
    """Class to be instantiated by the UPF charm providing the 5G UPF Interface."""

    def __init__(self, charm: CharmBase, relationship_name: str):
        """Init."""
        super().__init__(charm, relationship_name)
        self.relationship_name = relationship_name
        self.charm = charm

    def set_upf_information(
        self,
        upf_ipv4_address: str,
        upf_fqdn: str,
        relation_id: int,
    ) -> None:
        """Sets UPF information in relation data.

        Args:
            upf_ipv4_address: UPF address
            upf_fqdn: UPF FQDN
            relation_id: Relation ID

        Returns:
            None
        """
        relation = self.model.get_relation(self.relationship_name, relation_id=relation_id)
        if not relation:
            raise RuntimeError(f"Relation {self.relationship_name} not created yet.")
        relation.data[self.charm.app].update(
            {
                "upf_ipv4_address": upf_ipv4_address,
                "upf_fqdn": upf_fqdn,
            }
        )
