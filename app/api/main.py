from fastapi import FastAPI, HTTPException, Depends, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
from typing import List, Dict, Any, Optional

from app.core.config import config
from app.services.openai_service import OpenAIService
from app.services.snmp_service import SNMPService
from app.services.mib_service import MIBService
from app.models.query import SNMPQuery, SNMPResponse
from app.utils.cache import get_cache, set_cache, clear_cache

# Initialize application
app = FastAPI(
    title=config.app_name,
    description="AI-powered SNMP query system",
    version="1.0.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
openai_service = OpenAIService()
mib_service = MIBService()
snmp_service = SNMPService(mib_service=mib_service)


@app.get("/")
async def root():
    """Health check endpoint"""
    return {"status": "online", "app_name": config.app_name}


@app.post("/query")
async def process_query(
    query: str = Body(..., description="Natural language SNMP query"),
    skip_cache: bool = Query(False, description="Skip cache lookup")
):
    """
    Process a natural language SNMP query
    """
    try:
        logger.info(f"Received query: {query}")

        # Check cache
        if not skip_cache:
            cache_key = f"query_{hash(query)}"
            cached_response = get_cache(cache_key)
            if cached_response:
                logger.info(f"Returning cached response for query: {query}")
                return cached_response

        # Process query with OpenAI
        snmp_query = await openai_service.process_query(query)

        if not snmp_query:
            raise HTTPException(status_code=400, detail="Failed to parse query")

        # Store original query
        snmp_query.raw_query = query

        # Execute SNMP query
        snmp_response_data = await snmp_service.execute_query(snmp_query)

        # Format response
        if "error" in snmp_response_data:
            formatted_response = SNMPResponse(
                raw_data=snmp_response_data,
                summary=f"Error: {snmp_response_data['error']}",
                query=query,
                error=snmp_response_data["error"]
            )
        else:
            # Use OpenAI to generate a summary
            formatted_response = await openai_service.format_response(snmp_response_data, query)

        # Cache response
        if not skip_cache and not formatted_response.error:
            cache_key = f"query_{hash(query)}"
            set_cache(cache_key, formatted_response.dict())

        return formatted_response.dict()

    except Exception as e:
        logger.error(f"Error processing query: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")


@app.get("/mibs")
async def get_mibs():
    """
    Get a list of loaded MIBs
    """
    try:
        mibs = mib_service.get_loaded_mibs()
        return {"mibs": mibs, "count": len(mibs)}
    except Exception as e:
        logger.error(f"Error getting MIBs: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting MIBs: {str(e)}")


@app.post("/mibs/upload")
async def upload_mib(file_path: str = Body(..., description="Path to MIB file")):
    """
    Upload a new MIB file
    """
    try:
        success = mib_service.add_mib_file(file_path)
        if success:
            # Clear MIB-related cache
            clear_cache(key_prefix="mib_")
            return {"status": "success", "message": f"MIB file added successfully"}
        else:
            raise HTTPException(status_code=400, detail="Failed to add MIB file")
    except Exception as e:
        logger.error(f"Error uploading MIB: {e}")
        raise HTTPException(status_code=500, detail=f"Error uploading MIB: {str(e)}")


@app.post("/oid/resolve")
async def resolve_oid(name: str = Body(..., description="OID name to resolve")):
    """
    Resolve an OID name to a numeric OID
    """
    try:
        oid = mib_service.resolve_oid(name)
        if oid:
            return {"name": name, "oid": oid}
        else:
            raise HTTPException(status_code=404, detail=f"OID not found: {name}")
    except Exception as e:
        logger.error(f"Error resolving OID: {e}")
        raise HTTPException(status_code=500, detail=f"Error resolving OID: {str(e)}")


@app.post("/oid/translate")
async def translate_oid(oid: str = Body(..., description="Numeric OID to translate")):
    """
    Translate a numeric OID to a symbolic name
    """
    try:
        name = mib_service.translate_oid(oid)
        if name:
            return {"oid": oid, "name": name}
        else:
            raise HTTPException(status_code=404, detail=f"OID not found: {oid}")
    except Exception as e:
        logger.error(f"Error translating OID: {e}")
        raise HTTPException(status_code=500, detail=f"Error translating OID: {str(e)}")


@app.post("/clear-cache")
async def clear_application_cache(prefix: Optional[str] = Query(None, description="Cache key prefix")):
    """
    Clear application cache
    """
    try:
        clear_cache(key_prefix=prefix)
        return {"status": "success", "message": "Cache cleared successfully"}
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        raise HTTPException(status_code=500, detail=f"Error clearing cache: {str(e)}")
