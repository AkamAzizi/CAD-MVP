import os
import json

def run(doc, parts_count, bbox, filename):
    """
    Analyze assembly and determine what it is and what views it should have.
    Uses deterministic analysis with optional AI enhancement for better identification.
    """
    if doc is None:
        return {
            "description": "Unknown assembly",
            "recommended_views": {"front": (0, 0, 1), "top": (0, 1, 0), "right": (1, 0, 0), "iso": (1, 1, 1)},
            "reasoning": ["No document available for analysis"]
        }
    
    # Step 1: Deterministic geometric analysis (always accurate)
    is_assembly = parts_count > 1
    is_single_part = parts_count == 1
    
    # Analyze bounding box to determine primary orientation
    primary_axis = None
    aspect_ratios = {}
    if bbox and bbox.get("x") and bbox.get("y") and bbox.get("z"):
        try:
            x = float(bbox["x"])
            y = float(bbox["y"])
            z = float(bbox["z"])
            
            # Calculate aspect ratios
            if x > 0 and y > 0 and z > 0:
                aspect_ratios["xy"] = max(x, y) / min(x, y) if min(x, y) > 0 else 1
                aspect_ratios["xz"] = max(x, z) / min(x, z) if min(x, z) > 0 else 1
                aspect_ratios["yz"] = max(y, z) / min(y, z) if min(y, z) > 0 else 1
                
                # Determine primary axis (longest dimension)
                if x >= y and x >= z:
                    primary_axis = "x"
                elif y >= z:
                    primary_axis = "y"
                else:
                    primary_axis = "z"
        except (ValueError, TypeError):
            pass
    
    # Step 2: Base description from deterministic analysis
    description_parts = []
    
    if is_assembly:
        description_parts.append(f"Assembly with {parts_count} parts")
    else:
        description_parts.append("Single part")
    
    if primary_axis:
        axis_names = {"x": "X-axis", "y": "Y-axis", "z": "Z-axis"}
        description_parts.append(f"Primary orientation along {axis_names[primary_axis]}")
    
    # Step 3: AI-enhanced identification (optional, falls back to filename-based)
    use_ai = os.getenv("CAD_USE_AI_ANALYSIS", "false").lower() == "true"
    ai_description = None
    
    if use_ai:
        try:
            ai_description = _get_ai_enhanced_description(
                filename, parts_count, is_assembly, primary_axis, aspect_ratios
            )
        except Exception as e:
            print(f"AI enhancement failed: {e}, using deterministic analysis")
    
    # Use AI description if available, otherwise use filename-based
    if ai_description:
        description = ai_description
    else:
        # Fallback: filename-based identification
        filename_lower = filename.lower() if filename else ""
        if "strut" in filename_lower:
            description_parts.append("Strut/stiffener component")
        elif "manifold" in filename_lower:
            description_parts.append("Manifold assembly")
        elif "pump" in filename_lower:
            description_parts.append("Pump-related component")
        elif "bracket" in filename_lower:
            description_parts.append("Bracket/mounting component")
        elif "frame" in filename_lower:
            description_parts.append("Frame structure")
        elif "mount" in filename_lower:
            description_parts.append("Mounting component")
        elif "support" in filename_lower or "bracket" in filename_lower:
            description_parts.append("Support structure")
        
        description = ". ".join(description_parts) if description_parts else "CAD assembly"
    
    # Step 4: Determine recommended views based on geometry (deterministic)
    recommended_views = {}
    reasoning = []
    
    # Standard views - always include
    recommended_views["iso"] = (1, 1, 1)
    reasoning.append("Isometric view for overall visualization")
    
    # Orthographic views based on primary axis
    if primary_axis == "x":
        recommended_views["front"] = (0, 0, 1)
        recommended_views["top"] = (0, 1, 0)
        recommended_views["right"] = (1, 0, 0)
        reasoning.append(f"Primary axis is X: front view shows YZ plane, top shows XY plane")
    elif primary_axis == "y":
        recommended_views["front"] = (0, 0, 1)
        recommended_views["top"] = (0, 1, 0)
        recommended_views["right"] = (1, 0, 0)
        reasoning.append(f"Primary axis is Y: front view shows XZ plane, top shows XY plane")
    else:
        recommended_views["front"] = (0, 0, 1)
        recommended_views["top"] = (0, 1, 0)
        recommended_views["right"] = (1, 0, 0)
        reasoning.append("Standard orthographic views (front, top, right)")
    
    # Add detail views for assemblies
    if is_assembly and parts_count > 5:
        reasoning.append(f"Assembly has {parts_count} parts - additional detail views may be helpful")
    
    return {
        "description": description,
        "parts_count": parts_count,
        "primary_axis": primary_axis,
        "aspect_ratios": aspect_ratios,
        "recommended_views": recommended_views,
        "reasoning": reasoning,
        "is_assembly": is_assembly,
        "ai_enhanced": ai_description is not None
    }


def _get_ai_enhanced_description(filename, parts_count, is_assembly, primary_axis, aspect_ratios):
    """Use AI to enhance assembly description. Returns enhanced description or None if fails."""
    try:
        ai_provider = os.getenv("CAD_AI_PROVIDER", "openai").lower()
        
        if ai_provider == "openai":
            import openai
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                return None
            
            client = openai.OpenAI(api_key=api_key)
            
            example_text = f'Automotive strut assembly designed for chassis reinforcement, optimized for X-axis load bearing with {parts_count} interconnected components.'
            prompt = f"""Based on this CAD file information, provide a concise, professional description (1-2 sentences):

- Filename: {filename}
- Parts: {parts_count} ({'Assembly' if is_assembly else 'Single part'})
- Primary orientation: {primary_axis}-axis
- Aspect ratios: {json.dumps(aspect_ratios)}

Provide ONLY a brief description of what this component/assembly likely is and its probable use case. Be specific and technical.
Example: {example_text}"""
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a CAD engineering expert. Provide concise technical descriptions."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=150
            )
            
            return response.choices[0].message.content.strip()
            
        elif ai_provider == "claude":
            import anthropic
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                return None
            
            client = anthropic.Anthropic(api_key=api_key)
            
            prompt = f"""Based on this CAD file information, provide a concise, professional description (1-2 sentences):

- Filename: {filename}
- Parts: {parts_count} ({'Assembly' if is_assembly else 'Single part'})
- Primary orientation: {primary_axis}-axis
- Aspect ratios: {json.dumps(aspect_ratios)}

Provide ONLY a brief description of what this component/assembly likely is and its probable use case. Be specific and technical."""
            
            message = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=150,
                temperature=0.3,
                system="You are a CAD engineering expert. Provide concise technical descriptions.",
                messages=[{"role": "user", "content": prompt}]
            )
            
            return message.content[0].text.strip()
            
    except Exception as e:
        print(f"AI enhancement error: {e}")
        return None
    
    return None
