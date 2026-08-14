import logging
from typing import Dict, Optional

from PIL import Image

from ..schemas import ImageAnalysis  # noqa: F401 – kept for re-export convenience
from .image_parser import ImageParser
from .structure_designer import StructureDesigner
from .crochet_params import CrochetParamsGenerator

logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    """Orchestrate the full photo-to-pattern pipeline."""

    def __init__(
        self,
        openai_key: Optional[str] = None,
        anthropic_key: Optional[str] = None,
    ):
        self.parser = ImageParser(
            openai_key=openai_key,
            anthropic_key=anthropic_key,
        )
        self.structure_designer = StructureDesigner()
        self.params_generator = CrochetParamsGenerator()

    def run_full_pipeline(self, image: Image.Image) -> Dict:
        """Run the complete pipeline: parse → design → generate params.

        Args:
            image: PIL Image to analyze

        Returns:
            Dict with 'analysis', 'structure', and 'params' keys
        """
        logger.info("Pipeline started")

        # Step 1: Vision parsing
        logger.info("Step 1/3: Parsing image with Vision API...")
        analysis = self.parser.parse_image(image)
        logger.info("Image parsed: %s body, %d parts", analysis.body_type, len(analysis.parts))

        # Step 2: 3D structure design
        logger.info("Step 2/3: Designing 3D structure...")
        structure = self.structure_designer.design_3d_structure(analysis)
        logger.info("Structure designed: %d parts", len(structure.get("parts", [])))

        # Step 3: Crochet parameter generation
        logger.info("Step 3/3: Generating crochet parameters...")
        params = self.params_generator.generate_params(analysis, structure)
        logger.info("Parameters generated: %d parts, difficulty=%s",
                    len(params.get("parts", [])), params.get("difficulty"))

        return {
            "analysis": analysis.model_dump(),
            "structure": structure,
            "params": params,
        }