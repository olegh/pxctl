from typing import List, Set
import ipaddress

import netifaces

from .enums import PrinterType


class NetworkUtils:
    @staticmethod
    def get_all_ipv4_broadcast_addresses() -> Set[str]:
        """Gets all ipv4 broadcast addresses

        Returns:
            Set[str]: all broadcast addresses
        """
        broadcast_addresses = set()
        interfaces = netifaces.interfaces()
        for interface in interfaces:
            interface_data: dict = netifaces.ifaddresses(interface)
            for data_values in interface_data.values():
                for data in data_values:
                    if not(broadcast_addr:=data.get("broadcast")):
                        continue
                    if not isinstance(ipaddress.ip_address(broadcast_addr), ipaddress.IPv4Address):
                        continue
                    broadcast_addresses.add(broadcast_addr)
        return broadcast_addresses


class MagicPicasoConverters:
    HW_to_type: List[PrinterType] = [
        PrinterType.none,
        PrinterType.none,
        PrinterType.none,
        PrinterType.none,
        PrinterType.DesignerXPro,
        PrinterType.DesignerX,
        PrinterType.DesignerXL,
        PrinterType.DesignerXLPro,
        PrinterType.DesignerXLPro,
        PrinterType.DesignerClassic,
        PrinterType.DesignerClassicAdv,
        PrinterType.DesignerX2,
        PrinterType.DesignerXPro2,
        PrinterType.none,
        PrinterType.DesignerXLPro2,
        PrinterType.DesignerXL2,
        PrinterType.DesignerXPro
    ]
    
    @classmethod
    def convert_hi_hw_ver_to_printer_model(cls, hi_hw_version) -> PrinterType:
        try:
            return cls.HW_to_type[hi_hw_version]
        except IndexError:
            return PrinterType.none
