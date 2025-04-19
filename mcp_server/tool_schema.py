import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Type

import jsonschema
from pydantic import BaseModel

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def validate_json_schema(schema: Dict[str, Any], data: Any) -> None:
    """
    Validate a Python data structure against a JSON schema.

    Raises:
        jsonschema.ValidationError: if data does not conform to schema.
    """
    try:
        jsonschema.validate(instance=data, schema=schema)
        logger.debug("JSON schema validation passed.")
    except jsonschema.ValidationError as e:
        logger.error(f"JSON schema validation error: {e.message}")
        raise


class MCPTool(ABC):
    """
    Abstract base class for Model Context Protocol (MCP) tools.

    Attributes:
        name: Unique name of the tool.
        description: Brief description of the tool's purpose.
        input_schema: Pydantic model class defining the input schema.
        output_schema: Pydantic model class defining the output schema.
    """

    name: str
    description: str
    input_schema: Type[BaseModel]
    output_schema: Type[BaseModel]

    def __init__(self) -> None:
        # Basic attribute checks
        if not getattr(self, 'name', None):
            raise ValueError("Tool must define a non-empty 'name'.")
        if not getattr(self, 'description', None):
            raise ValueError("Tool must define a non-empty 'description'.")
        if not isinstance(self.input_schema, type) or not issubclass(self.input_schema, BaseModel):
            raise TypeError("'input_schema' must be a Pydantic BaseModel subclass.")
        if not isinstance(self.output_schema, type) or not issubclass(self.output_schema, BaseModel):
            raise TypeError("'output_schema' must be a Pydantic BaseModel subclass.")
        logger.info(f"Initialized MCPTool: {self.name}")

    def parse_input(self, data: Dict[str, Any]) -> BaseModel:
        """
        Parse and validate raw input data into a Pydantic model.

        Returns:
            An instance of input_schema.

        Raises:
            pydantic.ValidationError: if data is invalid.
        """
        try:
            validated = self.input_schema(**data)
            logger.debug(f"Input parsed successfully for tool '{self.name}'.")
            return validated
        except Exception as e:
            logger.error(f"Error parsing input for '{self.name}': {e}")
            raise

    def format_output(self, data: Any) -> Dict[str, Any]:
        """
        Validate and serialize output data using Pydantic.

        Returns:
            A JSON-serializable dict.

        Raises:
            pydantic.ValidationError: if output data is invalid.
        """
        try:
            model = self.output_schema(**(data or {}))
            logger.debug(f"Output formatted successfully for tool '{self.name}'.")
            return model.dict()
        except Exception as e:
            logger.error(f"Error formatting output for '{self.name}': {e}")
            raise

    @classmethod
    def validate_json(cls, data: Any, schema_model: Type[BaseModel]) -> None:
        """
        Dynamically validate arbitrary data against the JSON schema of a Pydantic model.

        Args:
            data: The data to validate.
            schema_model: A Pydantic model class whose JSON schema will be used.

        Raises:
            jsonschema.ValidationError: if data does not conform to the schema.
        """
        json_schema = schema_model.schema()
        validate_json_schema(json_schema, data)

    @abstractmethod
    def run(self, input_data: BaseModel) -> Dict[str, Any]:
        """
        Execute the tool's main logic.

        Args:
            input_data: Validated input as a Pydantic model.

        Returns:
            A dict containing output data compatible with output_schema.
        """
        pass