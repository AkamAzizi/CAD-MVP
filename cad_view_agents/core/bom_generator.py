"""
BOM (Bill of Materials) generator for technical drawings.
Extracts part metadata and generates BOM tables.
"""
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from .part_tree import PartTree, PartNode


@dataclass
class PartMetadata:
    """Metadata for a single part in the BOM."""
    part_id: str
    item_number: int
    name: str
    quantity: int = 1
    material: str = "N/A"
    description: str = ""
    additional_info: Dict = field(default_factory=dict)


@dataclass
class BOMTable:
    """Represents a BOM table with part information."""
    parts: List[PartMetadata]
    columns: List[str] = field(default_factory=lambda: ["Item", "Part Number", "Description", "Qty", "Material"])
    
    def to_dict(self) -> Dict:
        """Convert BOM table to dictionary for JSON export."""
        return {
            "columns": self.columns,
            "rows": [
                {
                    "item": part.item_number,
                    "part_number": part.part_id,
                    "description": part.name,
                    "quantity": part.quantity,
                    "material": part.material
                }
                for part in self.parts
            ]
        }
    
    def get_row_count(self) -> int:
        """Get number of rows in BOM table."""
        return len(self.parts)
    
    def get_max_widths(self) -> Dict[str, float]:
        """
        Calculate maximum width for each column (for table layout).
        
        Returns:
            Dictionary mapping column name -> max width in mm
        """
        widths = {col: 0.0 for col in self.columns}
        
        for part in self.parts:
            widths["Item"] = max(widths["Item"], len(str(part.item_number)) * 2.0)
            widths["Part Number"] = max(widths["Part Number"], len(part.part_id) * 1.5)
            widths["Description"] = max(widths["Description"], len(part.name) * 1.2)
            widths["Qty"] = max(widths["Qty"], len(str(part.quantity)) * 2.0)
            widths["Material"] = max(widths["Material"], len(part.material) * 1.2)
        
        # Add minimum widths
        min_widths = {
            "Item": 15.0,
            "Part Number": 30.0,
            "Description": 50.0,
            "Qty": 15.0,
            "Material": 30.0
        }
        
        for col, min_w in min_widths.items():
            widths[col] = max(widths[col], min_w)
        
        return widths


class BOMGenerator:
    """Generates Bill of Materials tables from part trees."""
    
    # Standard row height for BOM table (mm)
    ROW_HEIGHT = 6.0
    
    # Header row height (mm)
    HEADER_HEIGHT = 8.0
    
    # Column spacing (mm)
    COLUMN_SPACING = 5.0
    
    def __init__(self):
        """Initialize BOM generator."""
        pass
    
    def extract_part_metadata(self, part_tree: PartTree, 
                             item_numbers: Dict[str, int]) -> List[PartMetadata]:
        """
        Extract metadata for all parts in the assembly.
        
        Args:
            part_tree: PartTree instance
            item_numbers: Dictionary mapping part_id -> item_number
            
        Returns:
            List of PartMetadata objects
        """
        metadata_list = []
        parts = part_tree.get_part_list()
        
        # Count part quantities (same geometry hash = same part)
        part_counts: Dict[str, int] = {}
        part_groups: Dict[str, List[PartNode]] = {}
        
        for part in parts:
            geometry_hash = part.geometry_hash
            if geometry_hash not in part_counts:
                part_counts[geometry_hash] = 0
                part_groups[geometry_hash] = []
            part_counts[geometry_hash] += 1
            part_groups[geometry_hash].append(part)
        
        # Create metadata for unique parts
        processed_hashes = set()
        
        for part in parts:
            geometry_hash = part.geometry_hash
            
            # Only process once per unique geometry
            if geometry_hash in processed_hashes:
                continue
            processed_hashes.add(geometry_hash)
            
            # Get item number (use first part's item number for grouped parts)
            item_number = item_numbers.get(part.id, 0)
            
            # Extract material from metadata
            material = part.metadata.get("material", "N/A")
            if material == "" or material is None:
                material = "N/A"
            
            # Extract name
            name = part.name
            if not name or name == "":
                name = f"Part_{item_number}"
            
            # Get quantity
            quantity = part_counts.get(geometry_hash, 1)
            
            # Create description
            description = name
            if quantity > 1:
                description += f" (x{quantity})"
            
            # Create metadata
            metadata = PartMetadata(
                part_id=part.id,
                item_number=item_number,
                name=name,
                quantity=quantity,
                material=material,
                description=description,
                additional_info=part.metadata.copy()
            )
            
            metadata_list.append(metadata)
        
        # Sort by item number
        metadata_list.sort(key=lambda m: m.item_number)
        
        return metadata_list
    
    def generate_table(self, part_metadata: List[PartMetadata]) -> BOMTable:
        """
        Generate BOM table from part metadata.
        
        Args:
            part_metadata: List of PartMetadata objects
            
        Returns:
            BOMTable object
        """
        return BOMTable(parts=part_metadata)
    
    def place_table(self, sheet_size, bom_table: BOMTable) -> Tuple[float, float]:
        """
        Calculate BOM table position on sheet (standard: bottom-left).
        
        Args:
            sheet_size: SheetSize object
            bom_table: BOMTable object
            
        Returns:
            Tuple of (x, y) position in mm from bottom-left
        """
        # Standard BOM position: bottom-left corner
        # Account for margins
        margin = sheet_size.margin_mm
        
        x = margin
        y = margin
        
        return (x, y)
    
    def calculate_table_size(self, bom_table: BOMTable) -> Tuple[float, float]:
        """
        Calculate BOM table dimensions.
        
        Args:
            bom_table: BOMTable object
            
        Returns:
            Tuple of (width, height) in mm
        """
        max_widths = bom_table.get_max_widths()
        
        # Calculate total width
        total_width = sum(max_widths.values()) + self.COLUMN_SPACING * (len(bom_table.columns) - 1)
        
        # Calculate total height
        row_count = bom_table.get_row_count()
        total_height = self.HEADER_HEIGHT + (row_count * self.ROW_HEIGHT)
        
        return (total_width, total_height)
    
    def format_table_text(self, bom_table: BOMTable) -> List[List[str]]:
        """
        Format BOM table as text rows for display/export.
        
        Args:
            bom_table: BOMTable object
            
        Returns:
            List of rows, each row is a list of cell strings
        """
        rows = []
        
        # Header row
        rows.append(bom_table.columns)
        
        # Data rows
        for part in bom_table.parts:
            row = [
                str(part.item_number),
                part.part_id,
                part.description,
                str(part.quantity),
                part.material
            ]
            rows.append(row)
        
        return rows
