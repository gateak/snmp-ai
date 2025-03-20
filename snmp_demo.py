#!/usr/bin/env python3

import asyncio
import json
import sys
import time
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.syntax import Syntax
from rich.tree import Tree
from app.services.openai_service import OpenAIService
from app.services.snmp_service import SNMPService
from app.services.mib_service import MIBService
from app.models.query import SNMPQuery
from app.core.config import config

# Initialize Rich console for beautiful output
console = Console()

async def fetch_system_info(target_ip="192.168.97.14"):
    """
    Fetch system information from the target device using SNMP
    """
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]Querying system information..."),
        transient=True,
    ) as progress:
        progress.add_task("querying", total=None)

        # Initialize services
        openai_service = OpenAIService()
        snmp_service = SNMPService()
        mib_service = MIBService()

        # Query system MIB
        console.print(Panel(f"[bold cyan]SNMP-AI Demo - Device Analysis[/bold cyan]\n\nTarget Device: [bold]{target_ip}[/bold]",
                           expand=False, border_style="cyan"))

        # First query - system description
        console.print("\n[bold blue]Step 1:[/bold blue] Fetching basic system information")
        query_text = f"Get the system description, contact, name, location, and uptime from the device at {target_ip}"

        snmp_query = await openai_service.process_query(query_text)

        if not snmp_query:
            console.print("[bold red]Error:[/bold red] Failed to generate system info query")
            return None

        # Display generated query
        query_json = json.dumps(snmp_query.dict(), indent=2)
        console.print(Panel(Syntax(query_json, "json", theme="monokai", line_numbers=True),
                           title="Generated SNMP Query", border_style="green"))

        # Execute query
        with console.status(f"[bold green]Executing SNMP {snmp_query.operation.command} query...[/bold green]"):
            system_info = await snmp_service.execute_query(snmp_query)

        # Format and display result
        if "error" in system_info:
            console.print(f"[bold red]Error:[/bold red] {system_info['error']}")
            return None

        formatted_response = await openai_service.format_response(system_info, query_text)

        # Create a table for system information
        table = Table(title="System Information", show_header=True, header_style="bold magenta")
        table.add_column("Parameter", style="cyan")
        table.add_column("Value", style="green")

        for oid, value in system_info.items():
            oid_name = mib_service.translate_oid(oid) or oid
            table.add_row(oid_name, str(value))

        console.print(table)
        console.print(Panel(formatted_response.summary, title="AI Summary", border_style="blue"))

        return system_info

async def query_system_object_id(target_ip="192.168.97.14"):
    """
    Query the sysObjectID from the target device
    """
    console.print("\n[bold blue]Step 2:[/bold blue] Fetching sysObjectID for vendor identification")

    # Initialize services
    openai_service = OpenAIService()
    snmp_service = SNMPService()

    # Use OpenAI to generate the query
    query_text = f"Get the sysObjectID (1.3.6.1.2.1.1.2.0) from the device at {target_ip}"

    with console.status("[bold green]Generating SNMP query for sysObjectID...[/bold green]"):
        snmp_query = await openai_service.process_query(query_text)

    if not snmp_query:
        console.print("[bold red]Error:[/bold red] Failed to generate sysObjectID query")
        return None

    # Execute query
    with console.status("[bold green]Querying sysObjectID...[/bold green]"):
        result = await snmp_service.execute_query(snmp_query)

    if "error" in result:
        console.print(f"[bold red]Error:[/bold red] {result['error']}")
        return None

    object_id = next(iter(result.values()))
    console.print(f"[bold green]sysObjectID:[/bold green] {object_id}")

    # Look up vendor information based on the OID prefix
    vendor_oid_prefix = '.'.join(object_id.split('.')[:7])  # First 7 parts usually identify the vendor

    # Common enterprise OID mappings - this would ideally be pulled from a more comprehensive database
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

    vendor = vendor_mappings.get(vendor_oid_prefix, "Unknown Vendor")

    # Check if this is a Dahua device
    is_dahua = False
    sys_description = None

    # Try to get the system description to check for Dahua
    for oid, value in result.items():
        if "1.3.6.1.2.1.1.1.0" in oid:
            sys_description = str(value)
            break

    # Check for Dahua patterns
    if (sys_description and "IPC-HDBW" in sys_description) or vendor_oid_prefix == "1.3.6.1.4.1.1004849":
        vendor = "Dahua Technology"
        is_dahua = True
        console.print("[bold green]Dahua device detected![/bold green]")

    console.print(f"[bold green]Identified vendor:[/bold green] {vendor} ({vendor_oid_prefix})")

    return object_id, vendor, vendor_oid_prefix, is_dahua

async def query_enterprise_mibs(target_ip, vendor_oid_prefix, is_dahua=False):
    """
    Query enterprise-specific MIBs based on the vendor OID prefix
    """
    console.print("\n[bold blue]Step 3:[/bold blue] Exploring enterprise-specific MIBs")

    # Initialize services
    openai_service = OpenAIService()
    snmp_service = SNMPService()

    # Common enterprise MIB branches to check based on vendor
    enterprise_mibs = {
        "Common": [
            {"oid": "1.3.6.1.2.1.25.1.1.0", "description": "Host Resources - System Uptime"},
            {"oid": "1.3.6.1.2.1.25.2", "description": "Host Resources - Storage Information", "walk": True},
            {"oid": "1.3.6.1.2.1.25.3.2", "description": "Host Resources - Devices", "walk": True},
            {"oid": "1.3.6.1.2.1.31.1.1", "description": "IF-MIB - Interface Statistics", "walk": True},
            {"oid": "1.3.6.1.2.1.4.20", "description": "IP Addresses", "walk": True},
        ],
        "1.3.6.1.4.1.9": [  # Cisco
            {"oid": "1.3.6.1.4.1.9.9.13", "description": "Cisco Environmental Monitoring", "walk": True},
            {"oid": "1.3.6.1.4.1.9.9.109", "description": "Cisco CPU Utilization", "walk": True},
        ],
        "1.3.6.1.4.1.890": [  # HIKVISION
            {"oid": "1.3.6.1.4.1.890.1", "description": "HIKVISION Device Information", "walk": True},
        ],
        "1.3.6.1.4.1.8072": [  # Net-SNMP
            {"oid": "1.3.6.1.4.1.8072.1", "description": "Net-SNMP Agent", "walk": True},
        ],
        "1.3.6.1.4.1.1004849": [  # Dahua
            {"oid": "1.3.6.1.4.1.1004849.1", "description": "Dahua Device Information", "walk": True},
            {"oid": "1.3.6.1.4.1.1004849.2", "description": "Dahua System Status", "walk": True},
            {"oid": "1.3.6.1.4.1.1004849.3", "description": "Dahua Video Settings", "walk": True},
            {"oid": "1.3.6.1.4.1.1004849.4", "description": "Dahua Network Config", "walk": True},
            {"oid": "1.3.6.1.4.1.1004849.5", "description": "Dahua Alarm Events", "walk": True},
        ],
    }

    # Get vendor-specific MIBs and common MIBs
    mibs_to_query = enterprise_mibs.get("Common", [])
    if vendor_oid_prefix in enterprise_mibs:
        mibs_to_query.extend(enterprise_mibs[vendor_oid_prefix])

    # Add Dahua MIBs if it's a Dahua device but the OID doesn't match
    if is_dahua and vendor_oid_prefix != "1.3.6.1.4.1.1004849":
        console.print("[bold yellow]Adding Dahua-specific MIBs for detected Dahua device[/bold yellow]")
        mibs_to_query.extend(enterprise_mibs["1.3.6.1.4.1.1004849"])

    # Query each enterprise MIB
    results = {}
    tree = Tree("[bold magenta]Enterprise MIB Data[/bold magenta]")

    for mib in mibs_to_query:
        branch = tree.add(f"[cyan]{mib['description']}[/cyan]")

        # Generate query using OpenAI
        command = "WALK" if mib.get("walk", False) else "GET"
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
        else:
            # Add results to tree
            count = 0
            for oid, value in result.items():
                if count < 5:  # Limit display to 5 items per MIB
                    branch.add(f"[yellow]{oid}[/yellow]: {value}")
                    count += 1
                else:
                    if count == 5:
                        branch.add(f"[dim]... and {len(result) - 5} more items[/dim]")
                    count += 1

            # Store all results
            results[mib["oid"]] = result

    console.print(tree)
    return results

async def generate_report(system_info, vendor_data, enterprise_data):
    """
    Generate a comprehensive AI report about the device
    """
    console.print("\n[bold blue]Step 4:[/bold blue] Generating comprehensive device report")

    # Initialize OpenAI service
    openai_service = OpenAIService()

    # Combine all data into a single structure for the AI to analyze
    all_data = {
        "system_info": system_info,
        "vendor_info": vendor_data,
        "enterprise_data": {k: {oid: value for oid, value in v.items() if not isinstance(value, bytes)}
                          for k, v in enterprise_data.items() if isinstance(v, dict)}
    }

    # Adjust prompt based on device type
    device_type = "Dahua IP camera" if vendor_data.get("is_dahua_device", False) else "network device"
    query = f"Analyze all SNMP data from the {device_type} at 192.168.97.14 and provide a comprehensive technical report"

    with console.status("[bold green]AI is analyzing device data and generating report...[/bold green]"):
        # Using a different format to get a more detailed report
        messages = [
            {"role": "system", "content": "You are a network analysis expert specializing in SNMP data interpretation. Provide a detailed technical analysis of the provided SNMP data, identifying device capabilities, potential security concerns, and optimization recommendations."},
            {"role": "user", "content": f"Here is SNMP data from a {device_type} at 192.168.97.14:\n{json.dumps(all_data, indent=2)}\n\nProvide a comprehensive technical analysis."}
        ]

        # Call the OpenAI API directly for the report
        response = openai_service.client.chat.completions.create(
            model=openai_service.model,
            messages=messages,
            temperature=0.3,
            max_tokens=1500
        )

        report = response.choices[0].message.content

    # Display the report
    console.print(Panel(report, title="[bold]Executive Device Analysis Report[/bold]",
                       border_style="green", expand=True))

    return report

async def main():
    """Main demo function"""
    try:
        # Clear screen for better presentation
        console.clear()

        # Display title
        title = Panel(
            "[bold cyan]SNMP-AI[/bold cyan] [bold white]Executive Demo[/bold white]",
            border_style="cyan",
            expand=False
        )
        console.print(title, justify="center")
        console.print("\n[italic]Analyzing network device at 192.168.97.14 using AI-powered SNMP queries[/italic]\n")

        # Fetch basic system information
        system_info = await fetch_system_info()
        if not system_info:
            console.print("[bold red]Demo cannot continue without system information[/bold red]")
            return

        # Fetch sysObjectID and determine vendor
        vendor_info = await query_system_object_id()
        if not vendor_info:
            console.print("[bold red]Failed to determine vendor information[/bold red]")
            return

        # Unpack vendor info
        object_id, vendor, vendor_oid_prefix, is_dahua = vendor_info

        # Query enterprise MIBs
        enterprise_data = await query_enterprise_mibs("192.168.97.14", vendor_oid_prefix, is_dahua)

        # Generate comprehensive report
        vendor_data = {
            "sysObjectID": object_id,
            "vendor": vendor,
            "enterprise_oid": vendor_oid_prefix,
            "is_dahua_device": is_dahua
        }
        await generate_report(system_info, vendor_data, enterprise_data)

        # Conclusion
        console.print("\n[bold green]Demo completed successfully![/bold green]")
        console.print("[italic]Thank you for exploring the capabilities of SNMP-AI[/italic]")

    except Exception as e:
        console.print(f"[bold red]Error in demo:[/bold red] {str(e)}")
        import traceback
        console.print(traceback.format_exc())

if __name__ == "__main__":
    asyncio.run(main())
