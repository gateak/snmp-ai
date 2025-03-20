#!/usr/bin/env python3

import asyncio
import argparse
import json
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
from app.core.config import config

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
    "1.3.6.1.4.1.674.10892.5": "Dell iDRAC"
}

# Define enterprise-specific MIBs
ENTERPRISE_MIBS = {
    "Common": [
        {"oid": "1.3.6.1.2.1.1", "description": "System MIB", "walk": True},
        {"oid": "1.3.6.1.2.1.2", "description": "Interfaces MIB", "walk": True},
    ],
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
        {"oid": "1.3.6.1.4.1.674.10892.5.1", "description": "DELL-RAC-MIB::drsSystemInfo", "walk": True},
        {"oid": "1.3.6.1.4.1.674.10892.5.2", "description": "DELL-RAC-MIB::drsComponentInfo", "walk": True},
        {"oid": "1.3.6.1.4.1.674.10892.5.4", "description": "DELL-RAC-MIB::drsFaultInfo", "walk": True},
    ],
    "Unknown Vendor": [
        {"oid": "1.3.6.1.2.1.1", "description": "System MIB", "walk": True},
        {"oid": "1.3.6.1.2.1.2", "description": "Interfaces MIB", "walk": True},
        {"oid": "1.3.6.1.2.1.25", "description": "HOST-RESOURCES-MIB", "walk": True},
    ]
}

async def fetch_system_info(target_ip, community="public"):
    """
    Fetch system information from the target device using SNMP
    """
    console.print("\n[bold blue]Step 1:[/bold blue] Fetching basic system information")

    # Initialize services
    openai_service = OpenAIService()
    snmp_service = SNMPService()
    mib_service = MIBService()

    # Query system MIB
    query_text = f"Walk the System MIB (1.3.6.1.2.1.1) on device {target_ip} using SNMP version 2c and community string '{community}'"

    with console.status("[bold green]Generating SNMP query using AI...[/bold green]"):
        snmp_query = await openai_service.process_query(query_text)

    if not snmp_query:
        console.print("[bold red]Error:[/bold red] Failed to generate system info query")
        return None

    # Override community string if provided
    if community != "public":
        snmp_query.credentials.community = community

    # Execute query
    with console.status("[bold green]Querying System MIB...[/bold green]"):
        result = await snmp_service.execute_query(snmp_query)

    if "error" in result:
        console.print(f"[bold red]Error:[/bold red] {result['error']}")
        return None

    # Create a table to display system information
    sys_table = Table(title="System Information", show_header=True, header_style="bold magenta")
    sys_table.add_column("OID", style="cyan")
    sys_table.add_column("Value", style="green")

    # Variables to store important information
    sys_description = ""
    sys_object_id = ""

    for oid, value in result.items():
        oid_name = mib_service.translate_oid(oid) or oid
        sys_table.add_row(oid_name, str(value))

        if "sysDescr" in oid_name:
            sys_description = str(value)
        elif "sysObjectID" in oid_name:
            sys_object_id = str(value)

    console.print(sys_table)
    return result, sys_description, sys_object_id

async def analyze_system_data(sys_data, sys_description, sys_object_id):
    """
    Analyze system data to identify vendor and device type
    """
    console.print("\n[bold blue]Step 2:[/bold blue] Analyzing device information")

    if not sys_object_id:
        console.print("[bold red]Error:[/bold red] sysObjectID not found")
        return None, None, False

    # Extract vendor OID prefix
    vendor_oid_prefix = '.'.join(sys_object_id.split('.')[:7])  # First 7 parts usually identify the vendor
    vendor = VENDOR_MAPPINGS.get(vendor_oid_prefix, "Unknown Vendor")

    if vendor == "Unknown Vendor":
        #try the whole sysObjectID
        vendor_oid_prefix = sys_object_id
        vendor = VENDOR_MAPPINGS.get(vendor_oid_prefix, "Unknown Vendor")

    # Special device detection
    is_dahua = False
    is_dell_idrac = False

    # Check for Dell iDRAC
    if "idrac" in sys_description.lower() or "dell" in sys_description.lower() or vendor_oid_prefix == "1.3.6.1.4.1.674.10892.5":
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

    # Create vendor info dictionary
    vendor_info = {
        "vendor": vendor,
        "object_id": sys_object_id,
        "vendor_oid_prefix": vendor_oid_prefix,
        "is_dahua": is_dahua,
        "is_dell_idrac": is_dell_idrac
    }

    return vendor_info, vendor_oid_prefix, is_dahua

async def query_enterprise_mibs(target_ip, vendor_info, community="public"):
    """
    Query enterprise-specific MIBs based on identified vendor
    """
    console.print("\n[bold blue]Step 3:[/bold blue] Querying device-specific information")

    # Initialize services
    openai_service = OpenAIService()
    snmp_service = SNMPService()

    vendor = vendor_info["vendor"]
    vendor_oid_prefix = vendor_info["vendor_oid_prefix"]
    is_dahua = vendor_info["is_dahua"]
    is_dell_idrac = vendor_info["is_dell_idrac"]

    # Get vendor-specific MIBs and common MIBs
    mibs_to_query = ENTERPRISE_MIBS.get("Common", [])

    if vendor in ENTERPRISE_MIBS:
        mibs_to_query.extend(ENTERPRISE_MIBS[vendor])
    else:
        mibs_to_query.extend(ENTERPRISE_MIBS["Unknown Vendor"])

    # Add Dell iDRAC MIBs if detected but not matched by OID
    if is_dell_idrac and vendor != "Dell iDRAC":
        console.print("[bold yellow]Adding Dell iDRAC-specific MIBs[/bold yellow]")
        mibs_to_query.extend(ENTERPRISE_MIBS["Dell iDRAC"])

    # Add Dahua MIBs if detected but not matched by OID
    if is_dahua and vendor != "Dahua Technology":
        console.print("[bold yellow]Adding Dahua-specific MIBs[/bold yellow]")
        mibs_to_query.extend(ENTERPRISE_MIBS["Dahua Technology"])

    # Query each enterprise MIB
    results = {}
    tree = Tree(f"[bold magenta]Enterprise MIB Data for {vendor}[/bold magenta]")

    for mib in mibs_to_query:
        branch = tree.add(f"[cyan]{mib['description']}[/cyan]")

        # Generate query using OpenAI
        command = "WALK" if mib.get("walk", True) else "GET"
        query_text = f"{command} the {mib['description']} OID {mib['oid']} on device {target_ip} using SNMP version 2c and community string '{community}'"

        with console.status(f"[bold green]Generating query for {mib['description']}...[/bold green]"):
            snmp_query = await openai_service.process_query(query_text)

        if not snmp_query:
            branch.add(f"[red]Error: Failed to generate query for {mib['oid']}[/red]")
            continue

        # Override community string if provided
        if community != "public":
            snmp_query.credentials.community = community

        # Execute query
        with console.status(f"[bold green]Querying {mib['description']}...[/bold green]"):
            result = await snmp_service.execute_query(snmp_query)

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

            # Store all results
            results[mib["oid"]] = result

    console.print(tree)
    return results

async def generate_report(system_info, vendor_info, enterprise_data, report_type="standard"):
    """
    Generate a summary report of the device
    """
    console.print("\n[bold blue]Step 4:[/bold blue] Generating device analysis")

    # Combine all collected data
    all_data = {
        "system_info": system_info,
        "vendor_info": vendor_info,
        "enterprise_data": enterprise_data
    }

    # Initialize OpenAI service
    openai_service = OpenAIService()

    # Generate summary with OpenAI based on report type
    if report_type == "executive":
        summary_prompt = (
            f"Generate an executive summary of this {vendor_info['vendor']} device based on the SNMP data. "
            "Focus on business impact, security considerations, and high-level technical specifications. "
            "Format for a non-technical executive audience."
        )
    else:
        summary_prompt = (
            f"Generate a technical analysis summary of this {vendor_info['vendor']} device based on the SNMP data. "
            "Include device capabilities, potential security considerations, and key metrics. "
            "Format for an IT professional."
        )

    with console.status("[bold green]Generating AI-powered analysis...[/bold green]"):
        # OpenAI API call is synchronous in v1.0.0+, don't use await
        response = openai_service.client.chat.completions.create(
            model=openai_service.model,
            messages=[
                {"role": "system", "content": "You are a network analyst summarizing SNMP data."},
                {"role": "user", "content": f"{summary_prompt}\n\nData: {json.dumps(all_data, default=str)}"}
            ],
            temperature=0.3,
            max_tokens=1000
        )

    # Extract the response
    summary = response.choices[0].message.content

    # Display the summary
    console.print(Panel(
        summary,
        title=f"{'Executive' if report_type == 'executive' else 'Technical'} Analysis Summary",
        border_style="green",
        expand=False
    ))

    # Return the data and summary
    return {
        "data": all_data,
        "summary": summary
    }

async def run_discovery(target_ip, community="public", report_type="standard", output_file=None):
    """
    Run the complete device discovery process
    """
    # Show title banner
    title = "SNMP-AI Executive Demo" if report_type == "executive" else "SNMP-AI Device Discovery"
    console.print(Panel(
        f"[bold cyan]{title}[/bold cyan]\n\n"
        f"Target Device: [bold]{target_ip}[/bold]",
        border_style="cyan", expand=False
    ))

    # Step 1: Fetch system information
    system_info, sys_description, sys_object_id = await fetch_system_info(target_ip, community)
    if not system_info:
        return None

    # Step 2: Analyze system data
    vendor_info, vendor_oid_prefix, is_dahua = await analyze_system_data(system_info, sys_description, sys_object_id)
    if not vendor_info:
        return None

    # Step 3: Query enterprise MIBs
    enterprise_data = await query_enterprise_mibs(target_ip, vendor_info, community)

    # Step 4: Generate report
    result = await generate_report(system_info, vendor_info, enterprise_data, report_type)

    # Save to file if requested
    if output_file:
        with open(output_file, "w") as f:
            json.dump({
                "target_ip": target_ip,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "data": result["data"],
                "summary": result["summary"]
            }, f, indent=2, default=str)
        console.print(f"\n[bold green]Results saved to {output_file}[/bold green]")

    return result

async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="SNMP-AI: AI-powered SNMP device discovery")
    parser.add_argument("target", help="Target IP address or hostname")
    parser.add_argument("--community", "-c", default="public", help="SNMP community string (default: public)")
    parser.add_argument("--mode", "-m", choices=["standard", "executive", "discover"], default="standard",
                       help="Mode of operation (standard, executive, discover)")
    parser.add_argument("--output", "-o", help="Output file for results (JSON format)")

    args = parser.parse_args()

    try:
        await run_discovery(args.target, args.community, args.mode, args.output)
    except KeyboardInterrupt:
        console.print("\n[bold yellow]Operation cancelled by user[/bold yellow]")
    except Exception as e:
        console.print(f"\n[bold red]Error:[/bold red] {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())
