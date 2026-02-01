"""
AI-powered analysis agent for CAD assemblies.
Uses OpenAI GPT-4 or Claude to provide deeper insights for CAD engineers.
"""

import json
import os


def run(assembly_data, summary_data, trace_data):
    """
    Analyze CAD assembly using AI (OpenAI or Claude).
    
    Args:
        assembly_data: Output from assembly_analyzer_agent
        summary_data: Summary information (parts_count, bbox, filename, etc.)
        trace_data: Execution trace data
    
    Returns:
        AI analysis with insights for CAD engineers
    """
    
    # Check if AI analysis is enabled
    use_ai = os.getenv("CAD_USE_AI_ANALYSIS", "false").lower() == "true"
    ai_provider = os.getenv("CAD_AI_PROVIDER", "openai").lower()
    
    if not use_ai:
        return {
            "enabled": False,
            "message": "AI analysis disabled. Set CAD_USE_AI_ANALYSIS=true to enable."
        }
    
    # Handle None summary_data
    if summary_data is None:
        summary_data = {}
    
    if trace_data is None:
        trace_data = []
    
    # Prepare context for AI
    context = {
        "assembly_info": {
            "description": assembly_data.get("description", "Unknown") if assembly_data else "Unknown",
            "parts_count": assembly_data.get("parts_count", 0) if assembly_data else 0,
            "is_assembly": assembly_data.get("is_assembly", False) if assembly_data else False,
            "primary_axis": assembly_data.get("primary_axis") if assembly_data else None,
            "aspect_ratios": assembly_data.get("aspect_ratios", {}) if assembly_data else {},
            "reasoning": assembly_data.get("reasoning", []) if assembly_data else []
        },
        "geometry_info": {
            "parts_count": summary_data.get("parts_count", 0),
            "bbox": summary_data.get("bbox", {}),
            "filename": summary_data.get("filename", "")
        },
        "pipeline_info": {
            "agent_count": len([t for t in trace_data if t.get("agent")]) if trace_data else 0,
            "execution_successful": summary_data.get("qa", {}).get("status") == "pass" if summary_data.get("qa") else True
        }
    }
    
    try:
        if ai_provider == "openai":
            return _analyze_with_openai(context)
        elif ai_provider == "claude":
            return _analyze_with_claude(context)
        else:
            return {
                "enabled": True,
                "error": f"Unknown AI provider: {ai_provider}. Use 'openai' or 'claude'"
            }
    except Exception as e:
        return {
            "enabled": True,
            "error": f"AI analysis failed: {str(e)}"
        }


def _analyze_with_openai(context):
    """Analyze using OpenAI GPT-4 mini."""
    try:
        import openai
    except ImportError:
        return {
            "enabled": True,
            "error": "OpenAI library not installed. Install with: pip install openai"
        }
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {
            "enabled": True,
            "error": "OPENAI_API_KEY environment variable not set"
        }
    
    client = openai.OpenAI(api_key=api_key)
    
    prompt = _build_analysis_prompt(context)
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert CAD engineer assistant. Analyze CAD assemblies and provide valuable insights for design engineers."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.3,
            max_tokens=1000
        )
        
        analysis_text = response.choices[0].message.content
        
        return {
            "enabled": True,
            "provider": "openai",
            "model": "gpt-4o-mini",
            "analysis": analysis_text,
            "insights": _extract_insights(analysis_text),
            "recommendations": _extract_recommendations(analysis_text)
        }
    except Exception as e:
        return {
            "enabled": True,
            "provider": "openai",
            "error": f"OpenAI API error: {str(e)}"
        }


def _analyze_with_claude(context):
    """Analyze using Claude API."""
    try:
        import anthropic
    except ImportError:
        return {
            "enabled": True,
            "error": "Anthropic library not installed. Install with: pip install anthropic"
        }
    
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return {
            "enabled": True,
            "error": "ANTHROPIC_API_KEY environment variable not set"
        }
    
    client = anthropic.Anthropic(api_key=api_key)
    
    prompt = _build_analysis_prompt(context)
    
    try:
        message = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1000,
            temperature=0.3,
            system="You are an expert CAD engineer assistant. Analyze CAD assemblies and provide valuable insights for design engineers.",
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )
        
        analysis_text = message.content[0].text
        
        return {
            "enabled": True,
            "provider": "claude",
            "model": "claude-3-5-sonnet-20241022",
            "analysis": analysis_text,
            "insights": _extract_insights(analysis_text),
            "recommendations": _extract_recommendations(analysis_text)
        }
    except Exception as e:
        return {
            "enabled": True,
            "provider": "claude",
            "error": f"Claude API error: {str(e)}"
        }


def _build_analysis_prompt(context):
    """Build prompt for AI analysis."""
    assembly = context["assembly_info"]
    geometry = context["geometry_info"]
    
    # Check if bounding box values are realistic
    bbox = geometry.get('bbox', {})
    bbox_valid = True
    try:
        if bbox.get('x') and float(bbox['x']) > 1e10:
            bbox_valid = False
    except:
        pass
    
    prompt = f"""Analyze this CAD assembly and provide valuable insights for a CAD engineer:

**Assembly Information:**
- Description: {assembly.get('description', 'Unknown')}
- Parts Count: {assembly.get('parts_count', 0)}
- Type: {"Assembly" if assembly.get('is_assembly') else "Single Part"}
- Primary Orientation: {assembly.get('primary_axis', 'Unknown')} axis
- Filename: {geometry.get('filename', 'Unknown')}
- AI Enhanced: {"Yes" if assembly.get('ai_enhanced') else "No (deterministic analysis)"}

**Geometry Details:**
- Bounding Box: {json.dumps(bbox, indent=2) if bbox_valid else "Invalid/unrealistic values detected"}
- Aspect Ratios: {json.dumps(assembly.get('aspect_ratios', {}), indent=2)}

**Analysis Reasoning:**
{chr(10).join('- ' + r for r in assembly.get('reasoning', []))}

Please provide:
1. **Design Assessment**: What type of component/assembly is this likely used for? Be specific about industry/application.
2. **Manufacturing Considerations**: Material recommendations, fabrication methods, assembly considerations.
3. **Design Quality**: Observations about geometry complexity, aspect ratios, potential design improvements.
4. **View Recommendations**: Validate current views and suggest any additional critical views needed.
5. **Potential Issues**: Design concerns, areas requiring review, manufacturing challenges.

Provide concise, actionable insights (2-3 sentences per section) that would be valuable for a CAD engineer working with this design."""
    
    return prompt


def _extract_insights(analysis_text):
    """Extract structured insights from AI analysis text."""
    insights = {
        "design_type": None,
        "manufacturing_notes": [],
        "quality_observations": [],
        "view_recommendations": [],
        "potential_issues": []
    }
    
    # Simple extraction (could be improved with regex or structured output)
    lines = analysis_text.split('\n')
    current_section = None
    
    for line in lines:
        line_lower = line.lower().strip()
        if 'design' in line_lower and ('type' in line_lower or 'assessment' in line_lower):
            current_section = 'design'
        elif 'manufacturing' in line_lower:
            current_section = 'manufacturing'
        elif 'quality' in line_lower:
            current_section = 'quality'
        elif 'view' in line_lower:
            current_section = 'views'
        elif 'issue' in line_lower or 'concern' in line_lower:
            current_section = 'issues'
        elif line.strip().startswith('-') or line.strip().startswith('•') or line.strip().startswith('*'):
            clean_line = line.strip().lstrip('- •*').strip()
            if current_section == 'manufacturing':
                insights["manufacturing_notes"].append(clean_line)
            elif current_section == 'quality':
                insights["quality_observations"].append(clean_line)
            elif current_section == 'views':
                insights["view_recommendations"].append(clean_line)
            elif current_section == 'issues':
                insights["potential_issues"].append(clean_line)
    
    return insights


def _extract_recommendations(analysis_text):
    """Extract recommendations from AI analysis."""
    recommendations = []
    lines = analysis_text.split('\n')
    
    for line in lines:
        if any(keyword in line.lower() for keyword in ['recommend', 'suggest', 'consider', 'should', 'important']):
            if line.strip() and not line.strip().startswith('#'):
                recommendations.append(line.strip())
    
    return recommendations[:5]  # Top 5 recommendations
