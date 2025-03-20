#!/usr/bin/env python3

import asyncio
import json
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

async def query_system_mib(target_ip="192.168.97.14"):
    """
    Query the entire System MIB from the target device
    """
    # Show title
    console.print(Panel(
        "[bold cyan]SNMP-AI Executive Demo[/bold cyan]\n\n"
        f"Target Device: [bold]{target_ip}[/bold]",
        border_style="cyan", expand=False
    ))

    console.print("\n[bold blue]Step 1:[/bold blue] Querying System MIB Information")

    # Initialize services
    openai_service = OpenAIService()
    snmp_service = SNMPService()
    mib_service = MIBService()

    # Use OpenAI to generate the query
    query_text = f"Walk the entire System MIB (1.3.6.1.2.1.1) on device {target_ip}"

    with console.status("[bold green]Generating SNMP query using AI...[/bold green]"):
        snmp_query = await openai_service.process_query(query_text)

    if not snmp_query:
        console.print("[bold red]Error:[/bold red] Failed to generate System MIB query")
        return None

    # Execute query
    with console.status("[bold green]Querying System MIB...[/bold green]"):
        result = await snmp_service.execute_query(snmp_query)

    if "error" in result:
        console.print(f"[bold red]Error:[/bold red] {result['error']}")
        return None

    # Create table for system information
    table = Table(title="System MIB Information", show_header=True, header_style="bold magenta", expand=True)
    table.add_column("OID", style="dim cyan", no_wrap=True)
    table.add_column("Name", style="cyan")
    table.add_column("Value", style="green")

    # Add rows for each OID
    for oid, value in sorted(result.items()):
        oid_name = mib_service.translate_oid(oid) or oid
        # Make sysObjectID stand out with bold
        if "sysObjectID" in oid_name:
            oid_name = f"[bold]{oid_name}[/bold]"
            value = f"[bold yellow]{value}[/bold yellow]"
        table.add_row(oid, oid_name, str(value))

    console.print(table)

    # Extract sysObjectID for later use
    sys_object_id = None
    for oid, value in result.items():
        if "1.3.6.1.2.1.1.2.0" in oid:
            sys_object_id = value
            break

    return result, sys_object_id

async def analyze_object_id(sys_object_id):
    """
    Analyze the sysObjectID to identify vendor information
    """
    if not sys_object_id:
        console.print("[bold red]Error:[/bold red] sysObjectID not found")
        return None

    console.print("\n[bold blue]Step 2:[/bold blue] Analyzing sysObjectID for vendor information")

    # Create a panel highlighting the sysObjectID
    oid_text = Text()
    oid_text.append("sysObjectID: ", style="green")
    oid_text.append(str(sys_object_id), style="bold yellow")

    console.print(Panel(oid_text, title="Object Identifier", border_style="green"))

    # Common enterprise OID mappings
    vendor_mappings = {
        "1.3.6.1.4.1.9": "Cisco Systems",
        "1.3.6.1.4.1.311": "Microsoft",
        "1.3.6.1.4.1.2636": "Juniper Networks",
        "1.3.6.1.4.1.25461": "Palo Alto Networks",
        "1.3.6.1.4.1.3375": "F5 Networks",
        "1.3.6.1.4.1.4526": "Netgear",
        "1.3.6.1.4.1.890": "HIKVISION",
        "1.3.6.1.4.1.41112": "Ubiquiti Networks",
        "1.3.6.1.4.1.8072": "Net-SNMP",
        "1.3.6.1.4.1.1004849": "Dahua Technology"
    }

    # Check for Dahua device specifically based on description
    is_dahua = False
    str_object_id = str(sys_object_id)

    # Extract vendor OID prefix
    vendor_oid_prefix = '.'.join(str_object_id.split('.')[:7])  # First 7 parts
    vendor = vendor_mappings.get(vendor_oid_prefix, "Unknown Vendor")

    # Look for Dahua patterns in the system description or object ID
    if "IPC-HDBW" in str_object_id or vendor_oid_prefix == "1.3.6.1.4.1.1004849":
        vendor = "Dahua Technology"
        is_dahua = True
        console.print("[bold green]Dahua device detected![/bold green]")

    # Create vendor info table
    table = Table(title="Vendor Information", show_header=True, header_style="bold magenta")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Vendor OID Prefix", vendor_oid_prefix)
    table.add_row("Identified Vendor", f"[bold]{vendor}[/bold]")
    if is_dahua:
        table.add_row("Device Type", "[bold yellow]Dahua Camera[/bold yellow]")

    console.print(table)

    return vendor_oid_prefix, vendor, is_dahua

async def query_enterprise_mibs(target_ip, vendor_oid_prefix, vendor, is_dahua=False):
    """
    Query enterprise-specific MIBs based on the vendor
    """
    console.print("\n[bold blue]Step 3:[/bold blue] Exploring Enterprise MIBs")

    # Initialize services
    openai_service = OpenAIService()
    snmp_service = SNMPService()

    # Define enterprise MIBs based on vendor
    enterprise_mibs = {
        "Net-SNMP": [
            {"oid": f"{vendor_oid_prefix}.1", "description": "NET-SNMP-MIB::netSnmpObjects"},
            {"oid": f"{vendor_oid_prefix}.2", "description": "NET-SNMP-MIB::netSnmpModuleIDs"},
            {"oid": f"{vendor_oid_prefix}.3", "description": "NET-SNMP-MIB::netSnmpNotificationPrefix"},
        ],
        "HIKVISION": [
            {"oid": f"{vendor_oid_prefix}.1", "description": "HIKVISION-MIB::hikDevice"},
            {"oid": f"{vendor_oid_prefix}.2", "description": "HIKVISION-MIB::hikEvent"},
        ],
        "Cisco Systems": [
            {"oid": f"{vendor_oid_prefix}.9.9.13", "description": "CISCO-ENVMON-MIB::ciscoEnvMonObjects"},
            {"oid": f"{vendor_oid_prefix}.9.9.48", "description": "CISCO-MEMORY-POOL-MIB::ciscoMemoryPoolObjects"},
        ],
        "Dahua Technology": [
            {"oid": "1.3.6.1.4.1.1004849.1", "description": "DAHUA-MIB::dahuaDeviceInfo", "walk": True},
            {"oid": "1.3.6.1.4.1.1004849.2", "description": "DAHUA-MIB::dahuaSystemStatus", "walk": True},
            {"oid": "1.3.6.1.4.1.1004849.3", "description": "DAHUA-MIB::dahuaVideoSettings", "walk": True},
            {"oid": "1.3.6.1.4.1.1004849.4", "description": "DAHUA-MIB::dahuaNetworkConfig", "walk": True},
            {"oid": "1.3.6.1.4.1.1004849.5", "description": "DAHUA-MIB::dahuaAlarmEvents", "walk": True},
        ],
        "Unknown Vendor": [
            {"oid": vendor_oid_prefix, "description": "Enterprise MIB Root"},
        ]
    }

    # Get list of MIBs to query
    mibs_to_query = enterprise_mibs.get(vendor, enterprise_mibs["Unknown Vendor"])

    # If it's a Dahua device but identified differently, add Dahua MIBs
    if is_dahua and vendor != "Dahua Technology":
        console.print("[bold yellow]Adding Dahua-specific MIBs to the query list[/bold yellow]")
        mibs_to_query.extend(enterprise_mibs["Dahua Technology"])

    # Query each MIB
    results = {}
    tree = Tree(f"[bold magenta]Enterprise MIBs for {vendor}[/bold magenta]")

    for mib in mibs_to_query:
        # Create branch in the tree
        branch = tree.add(f"[cyan]{mib['description']}[/cyan]")

        # Generate query using OpenAI
        command = "WALK" if mib.get("walk", True) else "GET"  # Default to WALK for enterprise MIBs
        query_text = f"{command} the {mib['description']} OID {mib['oid']} on device {target_ip}"

        with console.status(f"[bold green]Generating query for {mib['description']}...[/bold green]"):
            snmp_query = await openai_service.process_query(query_text)

        if not snmp_query:
            branch.add(f"[red]Error: Failed to generate query for {mib['oid']}[/red]")
            continue

        # Execute query
        with console.status(f"[bold green]Querying {mib['description']}...[/bold green]"):
            result = await snmp_service.execute_query(snmp_query)

        if "error" in result:
            branch.add(f"[red]Error: {result['error']}[/red]")
        elif not result:
            branch.add("[yellow]No data returned[/yellow]")
        else:
            # Add results to tree
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

            # Store results
            results[mib["oid"]] = result

    console.print(tree)
    return results

async def generate_executive_summary(system_info, vendor_info, enterprise_data):
    """
    Generate an executive summary of the device information
    """
    console.print("\n[bold blue]Step 4:[/bold blue] Generating Executive Summary")

    # Initialize services
    openai_service = OpenAIService()

    # Combine all data
    all_data = {
        "system_info": system_info,
        "vendor_info": {
            "vendor": vendor_info["vendor"],
            "enterprise_oid": vendor_info["oid_prefix"],
            "is_dahua_device": vendor_info.get("is_dahua", False)
        },
        "enterprise_data": enterprise_data
    }

    # Create a summary prompt
    summary_prompt = (
        f"Generate an executive summary of the SNMP data collected from {all_data['vendor_info']['vendor']} device. "
        f"{'This is a Dahua camera security device. ' if all_data['vendor_info']['is_dahua_device'] else ''}"
        "Include key findings, device capabilities, and security recommendations. "
        "Format the response in a professional manner suitable for a CEO presentation."
    )

    with console.status("[bold green]Generating executive summary...[/bold green]"):
        # Using a different format for the summary
        messages = [
            {"role": "system", "content": "You are a network security expert presenting findings to a CEO. Your summaries are concise, insightful, and highlight business implications."},
            {"role": "user", "content": f"Here is SNMP data from a network device:\n{json.dumps(all_data, indent=2)}\n\n{summary_prompt}"}
        ]

        # Call the OpenAI API directly for a tailored summary
        response = openai_service.client.chat.completions.create(
            model=openai_service.model,
            messages=messages,
            temperature=0.3,
            max_tokens=1000
        )

        summary = response.choices[0].message.content

    # Display the summary
    console.print(Panel(summary, title="[bold]Executive Summary[/bold]", border_style="cyan", expand=True))

    return summary

async def main():
    """Main function for the SNMP-AI Executive Demo"""
    try:
        # Clear screen for better presentation
        console.clear()

        # Set target IP
        target_ip = "192.168.97.14"

        # Step 1: Query System MIB
        system_info, sys_object_id = await query_system_mib(target_ip)
        if not system_info:
            console.print("[bold red]Demo cannot continue without system information[/bold red]")
            return

        # Step 2: Analyze sysObjectID
        vendor_info = await analyze_object_id(sys_object_id)
        if not vendor_info:
            console.print("[bold red]Demo cannot continue without vendor information[/bold red]")
            return

        # Unpack vendor_info (now includes is_dahua flag)
        vendor_oid_prefix, vendor, is_dahua = vendor_info

        # Step 3: Query Enterprise MIBs (passing is_dahua flag)
        enterprise_data = await query_enterprise_mibs(target_ip, vendor_oid_prefix, vendor, is_dahua)

        # Step 4: Generate Executive Summary
        await generate_executive_summary(system_info, {"vendor": vendor, "oid_prefix": vendor_oid_prefix, "is_dahua": is_dahua}, enterprise_data)

        # Conclusion
        console.print("\n[bold green]✓ Demo completed successfully![/bold green]")
        console.print("[italic]Thank you for exploring the capabilities of SNMP-AI[/italic]")

    except Exception as e:
        console.print(f"[bold red]Error in demo:[/bold red] {str(e)}")
        import traceback
        console.print(traceback.format_exc())

if __name__ == "__main__":
    asyncio.run(main())
