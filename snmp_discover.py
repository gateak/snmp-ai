#!/usr/bin/env python3

import asyncio
import argparse
import sys
import time
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.syntax import Syntax
from rich.tree import Tree
from rich.text import Text
from app.services.openai_service import OpenAIService
from app.services.snmp_service import SNMPService
from app.services.mib_service import MIBService
from app.models.query import SNMPQuery

# Initialize Rich console for beautiful output
console = Console()

# Define enterprise OID mappings
VENDOR_MAPPINGS = {
    "1.3.6.1.4.1.9": "Cisco Systems",
    "1.3.6.1.4.1.311": "Microsoft",
    "1.3.6.1.4.1.2636": "Juniper Networks",
    "1.3.6.1.4.1.25461": "Palo Alto Networks",
    "1.3.6.1.4.1.3375": "F5 Networks",
    "1.3.6.1.4.1.4526": "Netgear",
    "1.3.6.1.4.1.890": "HIKVISION",
    "1.3.6.1.4.1.41112": "Ubiquiti Networks",
    "1.3.6.1.4.1.8072": "Net-SNMP",
    "1.3.6.1.4.1.1004849": "Dahua Technology",
    "1.3.6.1.4.1.674.10892.5": "Dell iDRAC"  # Dell iDRAC OID
}

# Define enterprise-specific MIBs
ENTERPRISE_MIBS = {
    "Net-SNMP": [
        {"oid": "1.3.6.1.4.1.8072.1", "description": "NET-SNMP-MIB::netSnmpObjects", "walk": True},
    ],
    "HIKVISION": [
        {"oid": "1.3.6.1.4.1.890.1", "description": "HIKVISION-MIB::hikDevice", "walk": True},
    ],
    "Cisco Systems": [
        {"oid": "1.3.6.1.4.1.9.9.13", "description": "CISCO-ENVMON-MIB::ciscoEnvMonObjects", "walk": True},
    ],
    "Dahua Technology": [
        {"oid": "1.3.6.1.4.1.1004849.1", "description": "DAHUA-MIB::dahuaDeviceInfo", "walk": True},
        {"oid": "1.3.6.1.4.1.1004849.2", "description": "DAHUA-MIB::dahuaSystemStatus", "walk": True},
    ],
    "Dell iDRAC": [
        {"oid": "1.3.6.1.4.1.674.10892.5.1.1", "description": "IDRAC-MIB::systemProperties", "walk": True},
        {"oid": "1.3.6.1.4.1.674.10892.5.1.3", "description": "IDRAC-MIB::systemStateInformation", "walk": True},
        {"oid": "1.3.6.1.4.1.674.10892.5.4", "description": "IDRAC-MIB::systemComponentGroups", "walk": True},
    ],
    "Unknown Vendor": [
        {"oid": "1.3.6.1.2.1.1", "description": "System MIB", "walk": True},
    ]
}

# Common MIBs to query for all devices
COMMON_MIBS = [
    {"oid": "1.3.6.1.2.1.1", "description": "System MIB (basic info)", "walk": True},
    {"oid": "1.3.6.1.2.1.2.2", "description": "Interfaces Table", "walk": True},
    {"oid": "1.3.6.1.2.1.4.20", "description": "IP Address Table", "walk": True},
]

async def discover_device(target_ip, community="public"):
    """
    Discover a device by querying its System MIB and identifying the vendor
    """
    # Show title
    console.print(Panel(
        f"[bold cyan]SNMP-AI Device Discovery[/bold cyan]\n\n"
        f"Target Device: [bold]{target_ip}[/bold]",
        border_style="cyan", expand=False
    ))

    # Initialize services
    openai_service = OpenAIService()
    snmp_service = SNMPService()
    mib_service = MIBService()

    # Step 1: Get the system information
    console.print("\n[bold blue]Step 1:[/bold blue] Querying basic system information")

    query_text = f"Get system description (sysDescr.0), name (sysName.0), object ID (sysObjectID.0), contact (sysContact.0), and uptime (sysUpTime.0) from the device at {target_ip} using SNMP version 2c and community string '{community}'"

    with console.status("[bold green]Generating SNMP query using AI...[/bold green]"):
        sys_info_query = await openai_service.process_query(query_text)

    if not sys_info_query:
        console.print("[bold red]Error:[/bold red] Failed to generate system info query")
        return None

    with console.status("[bold green]Querying device for basic information...[/bold green]"):
        sys_info_result = await snmp_service.execute_query(sys_info_query)

    if "error" in sys_info_result:
        console.print(f"[bold red]Error:[/bold red] {sys_info_result['error']}")
        console.print("[bold yellow]The device may not be reachable or SNMP may not be enabled.[/bold yellow]")
        return None

    # Display system information
    sys_table = Table(title="Basic Device Information", show_header=True, header_style="bold magenta")
    sys_table.add_column("Parameter", style="cyan")
    sys_table.add_column("Value", style="green")

    sys_description = ""
    sys_object_id = ""

    for oid, value in sys_info_result.items():
        oid_name = mib_service.translate_oid(oid) or oid
        sys_table.add_row(oid_name, str(value))

        if "sysDescr" in oid_name:
            sys_description = str(value)
        elif "sysObjectID" in oid_name:
            sys_object_id = str(value)

    console.print(sys_table)

    # Step 2: Identify vendor based on sysObjectID
    console.print("\n[bold blue]Step 2:[/bold blue] Identifying device vendor")

    vendor = "Unknown Vendor"
    vendor_oid_prefix = ""
    is_dahua = False
    is_dell_idrac = False

    if sys_object_id:
        # Extract vendor OID prefix
        vendor_oid_prefix = '.'.join(sys_object_id.split('.')[:7])  # First 7 parts usually identify the vendor
        vendor = VENDOR_MAPPINGS.get(vendor_oid_prefix, "Unknown Vendor")

        # Check for Dell iDRAC
        if "idrac" in sys_description.lower() or vendor_oid_prefix in "1.3.6.1.4.1.674.10892.5" or "dell" in sys_description.lower():
            vendor = "Dell iDRAC"
            is_dell_idrac = True
            console.print("[bold green]Dell iDRAC device detected![/bold green]")

        # Check for Dahua patterns
        elif "dahua" in sys_description.lower() or "ipc-" in sys_description.lower() or vendor_oid_prefix == "1.3.6.1.4.1.1004849":
            vendor = "Dahua Technology"
            is_dahua = True
            console.print("[bold green]Dahua device detected![/bold green]")

    # Create a panel showing vendor information
    vendor_panel = Panel(
        f"[bold green]Identified Vendor:[/bold green] {vendor}\n"
        f"[bold green]Vendor OID Prefix:[/bold green] {vendor_oid_prefix}",
        title="Vendor Identification",
        border_style="green"
    )
    console.print(vendor_panel)

    # Step 3: Get enterprise-specific MIBs
    console.print("\n[bold blue]Step 3:[/bold blue] Querying device-specific information")

    # Get vendor-specific MIBs
    mibs_to_query = COMMON_MIBS.copy()

    if vendor in ENTERPRISE_MIBS:
        mibs_to_query.extend(ENTERPRISE_MIBS[vendor])
    else:
        mibs_to_query.extend(ENTERPRISE_MIBS["Unknown Vendor"])

    # Add Dell iDRAC MIBs if detected
    if is_dell_idrac and vendor != "Dell iDRAC":
        console.print("[bold yellow]Adding Dell iDRAC-specific MIBs[/bold yellow]")
        mibs_to_query.extend(ENTERPRISE_MIBS["Dell iDRAC"])

    # Add Dahua MIBs if detected
    if is_dahua and vendor != "Dahua Technology":
        console.print("[bold yellow]Adding Dahua-specific MIBs[/bold yellow]")
        mibs_to_query.extend(ENTERPRISE_MIBS["Dahua Technology"])

    # Query each MIB
    enterprise_results = {}
    tree = Tree(f"[bold magenta]Device Information for {vendor}[/bold magenta]")

    for mib in mibs_to_query:
        branch = tree.add(f"[cyan]{mib['description']}[/cyan]")

        # Generate query using OpenAI
        command = "WALK" if mib.get("walk", True) else "GET"
        query_text = f"{command} the {mib['description']} OID {mib['oid']} on device {target_ip} using SNMP version 2c and community string '{community}'"

        with console.status(f"[bold green]Generating query for {mib['description']}...[/bold green]"):
            mib_query = await openai_service.process_query(query_text)

        if not mib_query:
            branch.add(f"[red]Error: Failed to generate query for {mib['oid']}[/red]")
            continue

        # Execute query
        with console.status(f"[bold green]Querying {mib['description']}...[/bold green]"):
            result = await snmp_service.execute_query(mib_query)

        if "error" in result:
            branch.add(f"[red]Error: {result['error']}[/red]")
        elif not result:
            branch.add("[yellow]No data returned[/yellow]")
        else:
            # Add results to tree (limit to avoid overwhelming output)
            count = 0
            for oid, value in sorted(result.items())[:10]:  # Limit to first 10
                if count < 5:
                    branch.add(f"[yellow]{oid}[/yellow]: {value}")
                    count += 1
                else:
                    remaining = len(result) - 5
                    if remaining > 0 and count == 5:
                        branch.add(f"[dim]... and {remaining} more items[/dim]")
                    count += 1

            enterprise_results[mib["oid"]] = result

    console.print(tree)

    # Step 4: Generate analysis summary
    console.print("\n[bold blue]Step 4:[/bold blue] Generating device analysis")

    # Combine all collected data
    all_data = {
        "system_info": sys_info_result,
        "vendor_info": {
            "vendor": vendor,
            "object_id": sys_object_id,
            "is_dahua": is_dahua,
            "is_dell_idrac": is_dell_idrac
        },
        "enterprise_data": enterprise_results
    }

    # Generate summary with OpenAI
    openai_service = OpenAIService()

    summary_prompt = (
        f"Generate a technical analysis summary of this {vendor} device based on the SNMP data. "
        "Include device capabilities, potential security considerations, and key metrics. "
        "Format for an IT professional."
    )

    with console.status("[bold green]Analyzing device data...[/bold green]"):
        messages = [
            {"role": "system", "content": "You are a network analysis expert specializing in SNMP data interpretation. Provide a detailed technical analysis focused on practical insights."},
            {"role": "user", "content": f"Here is SNMP data from a {vendor} device at {target_ip}:\n{sys_description}\n\n{summary_prompt}"}
        ]

        # Call OpenAI for analysis
        response = openai_service.client.chat.completions.create(
            model=openai_service.model,
            messages=messages,
            temperature=0.3,
            max_tokens=800
        )

        analysis = response.choices[0].message.content

    # Display the analysis
    console.print(Panel(analysis, title="[bold]Device Analysis[/bold]", border_style="cyan", expand=True))

    # Conclusion
    console.print("\n[bold green]✓ Device discovery completed![/bold green]")
    console.print(f"[italic]IP Address: {target_ip} | Vendor: {vendor}[/italic]")

    return all_data

async def main():
    """Main function to handle command-line arguments and run the discovery"""
    parser = argparse.ArgumentParser(description="SNMP-AI Device Discovery Tool")
    parser.add_argument("ip", help="IP address or hostname of the target device")
    parser.add_argument("-c", "--community", default="public", help="SNMP community string (default: public)")

    args = parser.parse_args()

    try:
        # Clear screen for better presentation
        console.clear()

        # Run discovery
        await discover_device(args.ip, args.community)

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        import traceback
        console.print(traceback.format_exc())
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
