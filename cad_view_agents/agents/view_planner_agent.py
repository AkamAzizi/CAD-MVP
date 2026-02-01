import os
import json

def run(assembly_analysis=None):
    """
    Generate view directions for rendering.
    If assembly_analysis is provided, can use AI to optimize views.
    Falls back to standard views if AI unavailable.
    """
    # Default standard views (always reliable)
    standard_views = {
        "front": (0, 0, 1),
        "top": (0, 1, 0),
        "right": (1, 0, 0),
        "iso": (1, 1, 1)
    }
    
    # If no assembly analysis provided, return standard views
    if not assembly_analysis:
        return {
            "views": standard_views,
            "source": "standard"
        }
    
    # Check if AI enhancement is enabled
    use_ai = os.getenv("CAD_USE_AI_ANALYSIS", "false").lower() == "true"
    
    if not use_ai:
        # Use views from assembly analyzer
        recommended_views = assembly_analysis.get("recommended_views", standard_views)
        return {
            "views": recommended_views,
            "source": "assembly_analyzer"
        }
    
    # Try AI-enhanced view planning
    try:
        ai_views = _get_ai_optimized_views(assembly_analysis)
        if ai_views:
            return {
                "views": ai_views,
                "source": "ai_enhanced"
            }
    except Exception as e:
        print(f"AI view planning failed: {e}, using assembly analyzer views")
    
    # Fallback to assembly analyzer views
    recommended_views = assembly_analysis.get("recommended_views", standard_views)
    return {
        "views": recommended_views,
        "source": "assembly_analyzer"
    }


def _get_ai_optimized_views(assembly_analysis):
    """Use AI to optimize view directions. Returns optimized views dict or None."""
    try:
        ai_provider = os.getenv("CAD_AI_PROVIDER", "openai").lower()
        
        description = assembly_analysis.get("description", "")
        parts_count = assembly_analysis.get("parts_count", 0)
        primary_axis = assembly_analysis.get("primary_axis")
        is_assembly = assembly_analysis.get("is_assembly", False)
        
        if ai_provider == "openai":
            import openai
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                return None
            
            client = openai.OpenAI(api_key=api_key)
            
            prompt = f"""As a CAD engineer, recommend optimal view directions for this component:

- Description: {description}
- Parts: {parts_count}
- Primary axis: {primary_axis}
- Type: {"Assembly" if is_assembly else "Single part"}

Respond with ONLY a JSON object with view directions as 3D vectors (x, y, z):
{{
  "front": [x, y, z],
  "top": [x, y, z],
  "right": [x, y, z],
  "iso": [x, y, z]
}}

Where vectors are normalized direction vectors (e.g., [0, 0, 1] for front, [1, 1, 1] for isometric).
Use standard orthographic views unless the geometry suggests better angles."""
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a CAD engineer. Respond with valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=200,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            
            # Convert lists to tuples and validate
            views = {}
            for key in ["front", "top", "right", "iso"]:
                if key in result and isinstance(result[key], list) and len(result[key]) == 3:
                    views[key] = tuple(result[key])
                else:
                    return None  # Invalid response, use fallback
            
            return views if len(views) == 4 else None
            
        elif ai_provider == "claude":
            import anthropic
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                return None
            
            client = anthropic.Anthropic(api_key=api_key)
            
            prompt = f"""As a CAD engineer, recommend optimal view directions for this component:

- Description: {description}
- Parts: {parts_count}
- Primary axis: {primary_axis}
- Type: {"Assembly" if is_assembly else "Single part"}

Respond with ONLY a JSON object with view directions as 3D vectors (x, y, z):
{{
  "front": [x, y, z],
  "top": [x, y, z],
  "right": [x, y, z],
  "iso": [x, y, z]
}}"""
            
            message = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=200,
                temperature=0.2,
                system="You are a CAD engineer. Respond with valid JSON only.",
                messages=[{"role": "user", "content": prompt}]
            )
            
            # Extract JSON from response
            text = message.content[0].text.strip()
            # Try to find JSON in the response
            import re
            json_match = re.search(r'\{[^}]*"front"[^}]*\}', text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
            else:
                result = json.loads(text)
            
            # Convert lists to tuples and validate
            views = {}
            for key in ["front", "top", "right", "iso"]:
                if key in result and isinstance(result[key], list) and len(result[key]) == 3:
                    views[key] = tuple(result[key])
                else:
                    return None
            
            return views if len(views) == 4 else None
            
    except Exception as e:
        print(f"AI view planning error: {e}")
        return None
    
    return None
