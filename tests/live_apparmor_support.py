"""Explicit AppArmor OS model; real kernel/lifecycle checks remain in production."""

from dataclasses import dataclass, field

from paper_radar.live_evidence.live_apparmor_kernel import ParserIdentity, SealedPolicy


@dataclass
class PolicyOS:
    expected: SealedPolicy | None = None
    parser: ParserIdentity | None = None
    profiles: dict[str, dict[str, bytes]] = field(default_factory=dict)
    writes: list[tuple[str, bytes]] = field(default_factory=list)
    revision_value: int = 1
    unavailable: bool = False

    def revision(self) -> bytes:
        if self.unavailable:
            raise PermissionError("synthetic policy readback unavailable")
        return str(self.revision_value).encode()

    def profile_handles(self) -> tuple[str, ...]:
        return tuple(sorted(self.profiles))

    def profile_identity(self, handle: str) -> tuple[str, ...]:
        return (handle, "synthetic-os-inode")

    def read_field(self, handle: str, field: str) -> bytes:
        return self.profiles[handle][field]

    def require_writer(self, parser: ParserIdentity) -> None:
        assert parser == self.parser

    def load_binary(self, binary: bytes) -> None:
        assert self.expected is not None
        self.writes.append(("add", binary))
        self.profiles.update(
            {
                str(index): {
                    "name": name.encode() + b"\n",
                    "mode": b"enforce\n",
                    "attach": attach.encode() + b"\n",
                    "raw_abi": self.expected.raw_abi.encode() + b"\n",
                    "raw_sha256": self.expected.binary_sha256.encode() + b"\n",
                    "raw_data": binary,
                }
                for index, (name, attach) in enumerate(self.expected.profiles)
            }
        )
        self.revision_value += 1

    def remove_profile(self, name: str) -> None:
        self.writes.append(("remove", name.encode()))
        for handle, fields in tuple(self.profiles.items()):
            if fields["name"] == name.encode() + b"\n":
                del self.profiles[handle]
        self.revision_value += 1
