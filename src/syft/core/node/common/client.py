from typing import List, Tuple

from syft.core.common.message import (
    EventualSyftMessageWithoutReply,
    ImmediateSyftMessageWithoutReply,
    ImmediateSyftMessageWithReply,
)
from .service.child_node_lifecycle_service import RegisterChildNodeMessage
from ...common.serde.deserialize import _deserialize
from syft.core.common.message import SignedMessage
from ..abstract.node import AbstractNodeClient
from ....decorators import syft_decorator
from ...io.location import Location
from ...common.uid import UID
from ...io.route import Route
from ....lib import lib_ast

# external class imports
from typing import Optional
from nacl.signing import SigningKey
from nacl.signing import VerifyKey

# external lib imports
import json


class Client(AbstractNodeClient):
    """Client is an incredibly powerful abstraction in Syft. We assume that,
    no matter where a client is, it can figure out how to communicate with
    the Node it is supposed to point to. If I send you a client I have
    with all of the metadata in it, you should have all the information
    you need to know to interact with a node (although you might not
    have permissions - clients should not store private keys)."""

    @syft_decorator(typechecking=True)
    def __init__(
        self,
        name: str,
        routes: List[Route],
        network: Optional[Location] = None,
        domain: Optional[Location] = None,
        device: Optional[Location] = None,
        vm: Optional[Location] = None,
        signing_key: Optional[SigningKey] = None,
        verify_key: Optional[VerifyKey] = None,
    ):
        super().__init__(network=network, domain=domain, device=device, vm=vm)

        self.name = name
        self.routes = routes
        self.default_route_index = 0

        # create a signing key if one isn't provided
        if signing_key is None:
            self.signing_key = SigningKey.generate()

        # if verify key isn't provided, get verify key from signing key
        if verify_key is None:
            self.verify_key = self.signing_key.verify_key
        else:
            self.verify_key = verify_key

        self.install_supported_frameworks()

    @staticmethod
    def deserialize_client_metadata_from_node(
        metadata: str,
    ) -> Tuple[Location, str, Location]:

        m_dict = json.loads(metadata)
        target_id = _deserialize(blob=m_dict["address"], from_json=True)
        name = m_dict["name"]
        id = _deserialize(blob=m_dict["id"], from_json=True)

        return target_id, name, id

    def install_supported_frameworks(self) -> None:
        self.lib_ast = lib_ast.copy()
        self.lib_ast.set_client(self)

        for attr_name, attr in self.lib_ast.attrs.items():
            setattr(self, attr_name, attr)

    def add_me_to_my_address(self) -> None:
        raise NotImplementedError

    @syft_decorator(typechecking=True)
    def register(self, client: AbstractNodeClient) -> None:
        msg = RegisterChildNodeMessage(child_node_client=client, address=self)

        if self.network is not None:
            client.network = (
                self.network
                if self.network is not None  # type: ignore # nested "is not None"
                else client.network
            )

        # QUESTION
        # if the client is a network and the domain is not none this will set it
        # on the network causing an exception
        # but we can't check if the client is a NetworkClient here because
        # this is a superclass of NetworkClient
        # Remove: if self.domain is not None:
        # then see the test line node_test.py:
        # bob_network_client.register(client=bob_domain_client)
        if self.domain is not None:
            client.domain = (
                self.domain
                if self.domain is not None  # type: ignore # nested "is not None"
                else client.domain
            )

        if self.device is not None:
            client.device = (
                self.device
                if self.device is not None  # type: ignore # nested "is not None"
                else client.device
            )

        if self.vm is not None:
            client.vm = self.vm

        self.send_immediate_msg_without_reply(msg=msg)

    @property
    def id(self) -> UID:
        """This client points to an node, this returns the id of that node."""
        raise NotImplementedError

    @syft_decorator(typechecking=True)
    def send_immediate_msg_with_reply(
        self, msg: ImmediateSyftMessageWithReply, route_index: int = 0
    ) -> ImmediateSyftMessageWithoutReply:
        route_index = route_index or self.default_route_index

        signed_msg = msg.sign(signing_key=self.signing_key)

        response = self.routes[route_index].send_immediate_msg_with_reply(msg=signed_msg)

        if response.is_valid:
            return response.message

        raise Exception("Response was signed by a fake key or was corrupted in transit.")

    @syft_decorator(typechecking=True)
    def send_immediate_msg_without_reply(
        self, msg: ImmediateSyftMessageWithoutReply, route_index: int = 0
    ) -> None:
        route_index = route_index or self.default_route_index

        signed_msg = msg.sign(signing_key=self.signing_key)

        self.routes[route_index].send_immediate_msg_without_reply(msg=signed_msg)

    @syft_decorator(typechecking=True)
    def send_eventual_msg_without_reply(
        self, msg: EventualSyftMessageWithoutReply, route_index: int = 0
    ) -> None:
        route_index = route_index or self.default_route_index

        signed_msg = msg.sign(signing_key=self.signing_key)

        self.routes[route_index].send_eventual_msg_without_reply(msg=signed_msg)

    @syft_decorator(typechecking=True)
    def __repr__(self) -> str:
        return f"<Client pointing to node with id:{self.id}>"

    @syft_decorator(typechecking=True)
    def register_route(self, route: Route) -> None:
        self.routes.append(route)

    @syft_decorator(typechecking=True)
    def set_default_route(self, route_index: int) -> None:
        self.default_route = route_index
