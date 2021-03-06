# Copyright (c) 2016-present, Facebook, Inc.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import argparse
import functools
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, NamedTuple, Optional

from .. import log
from ..analysis_directory import AnalysisDirectory
from ..configuration import Configuration
from .command import JSON, Command
from .stop import Stop


LOG: logging.Logger = logging.getLogger(__name__)


ROOT_PLACEHOLDER_NAME = "<root>"


class ServerDetails(NamedTuple):
    local_root: str
    pid: int
    server_pid_path: Path

    @staticmethod
    def _from_server_path(
        server_pid_path: Path, dot_pyre_root: Path
    ) -> "ServerDetails":
        return ServerDetails(
            pid=int(server_pid_path.read_text()),
            server_pid_path=server_pid_path,
            local_root=str(server_pid_path.relative_to(dot_pyre_root).parent.parent),
        )

    def is_root(self) -> bool:
        return self.local_root == "."

    @property
    def name(self) -> str:
        if self.is_root():
            return ROOT_PLACEHOLDER_NAME
        else:
            return self.local_root


@dataclass(frozen=True)
class ServersArguments:
    subcommand: Optional[str]


class Servers(Command):
    NAME: str = "servers"

    def __init__(
        self,
        arguments: argparse.Namespace,
        servers_arguments: ServersArguments,
        original_directory: str,
        configuration: Optional[Configuration] = None,
        analysis_directory: Optional[AnalysisDirectory] = None,
    ) -> None:
        super(Servers, self).__init__(
            arguments, original_directory, configuration, analysis_directory
        )
        self._servers_arguments = servers_arguments

    @staticmethod
    def from_arguments(
        arguments: argparse.Namespace,
        original_directory: str,
        configuration: Optional[Configuration] = None,
        analysis_directory: Optional[AnalysisDirectory] = None,
    ) -> "Servers":
        servers_arguments = ServersArguments(subcommand=arguments.servers_subcommand)
        return Servers(
            arguments,
            servers_arguments,
            original_directory,
            configuration,
            analysis_directory,
        )

    @classmethod
    def add_subparser(cls, parser: argparse._SubParsersAction) -> None:
        servers_parser = parser.add_parser(
            cls.NAME,
            epilog="""
            Command to manipulate multiple Pyre servers.
            """,
        )
        servers_parser.set_defaults(command=cls.from_arguments)
        subparsers = servers_parser.add_subparsers(dest="servers_subcommand")

        subparsers.add_parser("list", help="List running servers.")
        subparsers.add_parser("stop", help="Stop all running servers.")

    @staticmethod
    def _print_server_details(
        all_server_details: List[ServerDetails], output_format: str
    ) -> None:
        if output_format == JSON:
            server_details = [
                {"pid": details.pid, "name": details.name}
                for details in all_server_details
            ]
            log.stdout.write(json.dumps(server_details))
        else:
            if len(all_server_details) > 0:
                log.stdout.write(f"{'PID':<8}  project\n")
                for details in all_server_details:
                    log.stdout.write(f"{details.pid:<8}  {details.name}\n")
            else:
                log.stdout.write("No servers running")

    def _find_servers(self) -> List[Path]:
        return list(self._dot_pyre_directory.glob("**/server.pid"))

    def _all_server_details(self) -> List[ServerDetails]:
        return sorted(
            (
                ServerDetails._from_server_path(server_path, self._dot_pyre_directory)
                for server_path in self._find_servers()
            ),
            key=lambda details: details.local_root,
        )

    def _stop_servers(self, servers: List[ServerDetails]) -> None:
        for server in servers:
            LOG.warning("Stopping server for `%s` with pid %d", server.name, server.pid)
            Stop(
                arguments=self._arguments,
                original_directory=str(
                    Path(self._current_directory, server.local_root)
                ),
            ).run()

    def _run(self) -> None:
        all_server_details = self._all_server_details()

        subcommand = self._servers_arguments.subcommand
        if subcommand == "list" or subcommand is None:
            self._print_server_details(all_server_details, self._output)
        elif subcommand == "stop":
            self._stop_servers(all_server_details)
