import pytest
from pathlib import Path
from backend.app.validation.regression import RegressionRunner

@pytest.mark.asyncio
async def test_docx_format_regression_preservation(sample_docx_template: Path):
    runner = RegressionRunner()
    result = await runner.run_regression_test(
        template_path=str(sample_docx_template),
        prompt="Create an exact benchmark report on DeepMind AlphaGo"
    )

    assert result["document_type"] == "docx"
    assert result["passed"] is True
    assert result["hash_match"] is True
    assert len(result["issues"]) == 0
    assert result["original_style_hash"] == result["generated_style_hash"]

@pytest.mark.asyncio
async def test_pptx_format_regression_preservation(sample_pptx_template: Path):
    runner = RegressionRunner()
    result = await runner.run_regression_test(
        template_path=str(sample_pptx_template),
        prompt="Create a high-impact presentation on AI safety and ethics"
    )

    assert result["document_type"] == "pptx"
    assert result["passed"] is True
    assert result["hash_match"] is True
    assert len(result["issues"]) == 0
    assert result["original_style_hash"] == result["generated_style_hash"]
