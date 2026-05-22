from typing import Any

from bxengine.runtime.extensions.BxeExtension import BxeStatefulExtension, bpp_function


class DiscordStubExtension(BxeStatefulExtension):
    def __init__(self):
        self.buttons: list[list[str]] = []

    @bpp_function()
    def USERNAME(self) -> str:
        return "TestUser"

    @bpp_function()
    def USERID(self) -> int:
        return 0

    @bpp_function()
    def CHANNEL(self) -> int:
        return 0

    @bpp_function()
    def BUTTON(self, *args: Any) -> str:
        self.buttons.append(list(args))
        return ""
