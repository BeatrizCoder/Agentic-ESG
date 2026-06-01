"""Address validation tool using the ViaCEP public API."""

from crewai.tools import BaseTool
from pydantic import BaseModel, Field
import urllib.request
import urllib.error
import asyncio
import httpx
import json
import time
import logging
import re

logger = logging.getLogger(__name__)


class AddressValidationInput(BaseModel):
    cep: str = Field(
        description="Brazilian postal code (CEP) to validate. "
                    "Can be formatted as 01310-100 or 01310100."
    )


class AddressValidationTool(BaseTool):
    name: str = "Address Validation Tool"
    description: str = (
        "Validates a Brazilian postal code (CEP) and returns "
        "the full address (street, neighborhood, city, state). "
        "Use when customer mentions a CEP or delivery address. "
        "Input: CEP string. Output: address details or error."
    )
    args_schema: type[BaseModel] = AddressValidationInput

    timeout_seconds: int = 5
    max_retries: int = 2
    retry_delay: float = 1.0
    base_url: str = "https://viacep.com.br/ws/{cep}/json/"

    def _clean_cep(self, cep: str) -> str:
        return re.sub(r'\D', '', cep)

    def _validate_cep_format(self, cep: str) -> bool:
        return len(cep) == 8 and cep.isdigit()

    def _fetch_with_retry(self, url: str) -> dict:
        last_error = None

        for attempt in range(self.max_retries + 1):
            try:
                logger.info(
                    "AddressValidationTool: attempt %d/%d url=%s",
                    attempt + 1, self.max_retries + 1, url
                )
                start = time.time()

                req = urllib.request.Request(
                    url,
                    headers={"Accept": "application/json"}
                )

                with urllib.request.urlopen(
                    req, timeout=self.timeout_seconds
                ) as response:
                    data = json.loads(response.read().decode("utf-8"))
                    latency_ms = round((time.time() - start) * 1000, 2)
                    logger.info(
                        "AddressValidationTool: success latency=%sms",
                        latency_ms
                    )
                    return data

            except urllib.error.URLError as e:
                last_error = f"Network error: {e.reason}"
                logger.warning(
                    "AddressValidationTool: attempt %d failed: %s",
                    attempt + 1, last_error
                )
                if attempt < self.max_retries:
                    time.sleep(self.retry_delay)

            except TimeoutError:
                last_error = f"Timeout after {self.timeout_seconds}s"
                logger.warning(
                    "AddressValidationTool: timeout on attempt %d",
                    attempt + 1
                )
                if attempt < self.max_retries:
                    time.sleep(self.retry_delay)

            except json.JSONDecodeError:
                last_error = "Invalid response from ViaCEP API"
                break  # Don't retry on parse errors

        raise ConnectionError(last_error)

    def _run(self, cep: str) -> dict:
        start_time = time.time()

        clean_cep = self._clean_cep(cep)

        if not self._validate_cep_format(clean_cep):
            logger.warning(
                "AddressValidationTool: invalid CEP format: %s", cep
            )
            return {
                "valid": False,
                "cep": cep,
                "error": f"Invalid CEP format: '{cep}'. CEP must be 8 digits.",
                "error_type": "validation_error",
                "source": "viacep",
                "latency_ms": 0,
            }

        url = self.base_url.format(cep=clean_cep)

        try:
            data = self._fetch_with_retry(url)
            latency_ms = round((time.time() - start_time) * 1000, 2)

            if data.get("erro"):
                logger.info(
                    "AddressValidationTool: CEP not found: %s", clean_cep
                )
                return {
                    "valid": False,
                    "cep": clean_cep,
                    "error": f"CEP {clean_cep} not found in ViaCEP database.",
                    "error_type": "not_found",
                    "source": "viacep",
                    "latency_ms": latency_ms,
                }

            address = {
                "valid": True,
                "cep": data.get("cep", clean_cep),
                "street": data.get("logradouro", ""),
                "complement": data.get("complemento", ""),
                "neighborhood": data.get("bairro", ""),
                "city": data.get("localidade", ""),
                "state": data.get("uf", ""),
                "ibge": data.get("ibge", ""),
                "formatted": (
                    f"{data.get('logradouro', '')}, "
                    f"{data.get('bairro', '')}, "
                    f"{data.get('localidade', '')} - "
                    f"{data.get('uf', '')}"
                ),
                "source": "viacep",
                "latency_ms": latency_ms,
            }

            logger.info(
                "AddressValidationTool: validated CEP %s → %s",
                clean_cep, address["formatted"]
            )
            return address

        except ConnectionError as e:
            latency_ms = round((time.time() - start_time) * 1000, 2)
            logger.error(
                "AddressValidationTool: failed after retries: %s", e
            )
            return {
                "valid": False,
                "cep": clean_cep,
                "error": f"Could not reach ViaCEP API: {e}. Please try again later.",
                "error_type": "api_unavailable",
                "source": "viacep",
                "latency_ms": latency_ms,
                "fallback": "Address validation unavailable — proceeding without validation.",
            }

    async def _arun(self, cep: str) -> dict:
        start_time = time.time()
        cep_clean = self._clean_cep(cep)

        if not self._validate_cep_format(cep_clean):
            logger.warning("AddressValidationTool: invalid CEP format: %s", cep)
            return {
                "valid": False,
                "cep": cep,
                "error": f"Invalid CEP format: '{cep}'. CEP must be 8 digits.",
                "error_type": "validation_error",
                "source": "viacep",
                "latency_ms": 0,
            }

        url = self.base_url.format(cep=cep_clean)

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            for attempt in range(self.max_retries + 1):
                try:
                    logger.info(
                        "AddressValidationTool: async attempt %d/%d url=%s",
                        attempt + 1, self.max_retries + 1, url,
                    )
                    response = await client.get(
                        url, headers={"Accept": "application/json"}
                    )
                    response.raise_for_status()
                    data = response.json()
                    latency_ms = round((time.time() - start_time) * 1000, 2)

                    if data.get("erro"):
                        logger.info(
                            "AddressValidationTool: CEP not found: %s latency=%dms",
                            cep_clean, latency_ms,
                        )
                        return {
                            "valid": False,
                            "cep": cep_clean,
                            "error": f"CEP {cep_clean} not found in ViaCEP database.",
                            "error_type": "not_found",
                            "source": "viacep",
                            "latency_ms": latency_ms,
                        }

                    address = {
                        "valid": True,
                        "cep": data.get("cep", cep_clean),
                        "street": data.get("logradouro", ""),
                        "complement": data.get("complemento", ""),
                        "neighborhood": data.get("bairro", ""),
                        "city": data.get("localidade", ""),
                        "state": data.get("uf", ""),
                        "ibge": data.get("ibge", ""),
                        "formatted": (
                            f"{data.get('logradouro', '')}, "
                            f"{data.get('bairro', '')}, "
                            f"{data.get('localidade', '')} - "
                            f"{data.get('uf', '')}"
                        ),
                        "source": "viacep",
                        "latency_ms": latency_ms,
                    }
                    logger.info(
                        "ViaCEP: success %s → %s-%s latency=%dms",
                        cep_clean,
                        data.get("localidade"),
                        data.get("uf"),
                        latency_ms,
                    )
                    return address

                except httpx.TimeoutException:
                    logger.warning(
                        "AddressValidationTool: timeout attempt %d/%d",
                        attempt + 1, self.max_retries + 1,
                    )
                    if attempt == self.max_retries:
                        latency_ms = round((time.time() - start_time) * 1000, 2)
                        return {
                            "valid": False,
                            "cep": cep_clean,
                            "error": f"Timeout after {self.timeout_seconds}s",
                            "error_type": "api_unavailable",
                            "source": "viacep",
                            "latency_ms": latency_ms,
                            "fallback": "Address validation unavailable — proceeding without validation.",
                        }
                    await asyncio.sleep(self.retry_delay)

                except httpx.HTTPStatusError as e:
                    latency_ms = round((time.time() - start_time) * 1000, 2)
                    logger.error("AddressValidationTool: HTTP error %s", e)
                    return {
                        "valid": False,
                        "cep": cep_clean,
                        "error": str(e),
                        "error_type": "api_unavailable",
                        "source": "viacep",
                        "latency_ms": latency_ms,
                        "fallback": "Address validation unavailable — proceeding without validation.",
                    }

                except Exception as e:
                    latency_ms = round((time.time() - start_time) * 1000, 2)
                    logger.error(
                        "AddressValidationTool: unexpected error: %s", e, exc_info=True
                    )
                    return {
                        "valid": False,
                        "cep": cep_clean,
                        "error": str(e),
                        "error_type": "api_unavailable",
                        "source": "viacep",
                        "latency_ms": latency_ms,
                        "fallback": "Address validation unavailable — proceeding without validation.",
                    }

        latency_ms = round((time.time() - start_time) * 1000, 2)
        return {
            "valid": False,
            "cep": cep_clean,
            "error": "Max retries exceeded",
            "error_type": "api_unavailable",
            "source": "viacep",
            "latency_ms": latency_ms,
            "fallback": "Address validation unavailable — proceeding without validation.",
        }
