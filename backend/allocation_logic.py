import pandas as pd
from typing import Dict, List, Optional
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class StockBatch:
    def __init__(self, row: pd.Series):
        self.batch_number = row['Batch Number']
        self.weight = float(row['Stock Weight'].split()[0])  # Extract KG (e.g., "361.056 KG" → 361.056)
        self.material_id = row['Material ID']
        self.age = row['Real Stock Age']
        self.variety = row['Variety']
        self.ggn = row['GGN']
        self.origin = row['Origin Country']
        self.quality = row['Q3: Reinspection Quality']  # Updated column name
        self.supplier = row['Supplier']

    def matches_restrictions(self, restrictions: Dict) -> bool:
        """Check if this batch meets customer restrictions."""
        if restrictions.get('quality') and self.quality not in restrictions['quality']:
            return False
        if restrictions.get('origin') and self.origin not in restrictions['origin']:
            return False
        if restrictions.get('variety') and self.variety not in restrictions['variety']:
            return False
        if restrictions.get('ggn') and self.ggn != restrictions['ggn']:
            return False
        if restrictions.get('supplier') and self.supplier not in restrictions['supplier']:
            return False
        return True

def allocate_fruits(stock_df: pd.DataFrame, orders: List[Dict], restrictions: Dict) -> Dict:
    """
    Allocate stock to orders using FIFO, respecting restrictions.

    Args:
        stock_df (pd.DataFrame): Stock data from Excel or document.
        orders (List[Dict]): List of customer orders (e.g., {"customer_id": "C1", "fruit": "FIARGRN", "quantity": 200}).
        restrictions (Dict): Customer restrictions (quality, origin, variety, GGN, supplier).

    Returns:
        Dict: Allocation results per order (e.g., {"C1": {"status": "fully_allocated", "weight": 200, "batches": [...]}}).
    """
    # Convert stock to list of StockBatch objects, sorted by age (FIFO: oldest first)
    stock_batches = [StockBatch(row) for _, row in stock_df.sort_values('Real Stock Age', ascending=False).iterrows()]
    allocations = {}
    remaining_stock = stock_batches.copy()

    for order in orders:
        customer_id = order['customer_id']
        fruit_type = order['fruit']
        required_weight = order['quantity']
        allocated_weight = 0
        allocated_batches = []

        # Filter batches by material_id (fruit type)
        matching_batches = [b for b in remaining_stock if b.material_id == fruit_type]
        if not matching_batches:
            allocations[customer_id] = {"status": "unfulfilled", "weight": 0}
            continue

        for batch in matching_batches:
            if not batch.matches_restrictions(restrictions):
                continue
            if allocated_weight >= required_weight:
                break
            weight_to_allocate = min(required_weight - allocated_weight, batch.weight)
            allocated_weight += weight_to_allocate
            batch.weight -= weight_to_allocate
            allocated_batches.append({"batch": batch.batch_number, "weight": weight_to_allocate})

        if allocated_weight > 0:
            allocations[customer_id] = {
                "status": "fully_allocated" if allocated_weight == required_weight else "partially_allocated",
                "weight": allocated_weight,
                "batches": allocated_batches
            }
            # Remove or update batches with zero weight
            remaining_stock = [b for b in remaining_stock if b.weight > 0]
        else:
            allocations[customer_id] = {"status": "unfulfilled", "weight": 0}

    logger.info(f"Allocation completed: {json.dumps(allocations, indent=2)}")
    return allocations

if __name__ == "__main__":
    # Convert document data to DataFrame for testing
    stock_data = [
        {"Location": "", "Batch Number": "EX24000367", "Stock Weight": "0.008 KG", "Material ID": "FIARGRN", 
         "Real Stock Age": 23, "Variety": "BLUE RIBBON", "GGN": "4063061591012", "Origin Country": "Chile", 
         "Q3: Reinspection Quality": "", "BL/AWB/CMR": "27012025", "Allocation": "", "MinimumSize": 12, 
         "Origin Pallet Number": "FP00054676", "Supplier": "BERRY PACKING SERVICES BV"},
        # Add more rows from your document here (simplified for brevity)
        {"Location": "", "Batch Number": "EX24000536", "Stock Weight": "361.056 KG", "Material ID": "FIARGRN", 
         "Real Stock Age": 14, "Variety": "LEGACY", "GGN": "4059883818772", "Origin Country": "Chile", 
         "Q3: Reinspection Quality": "", "BL/AWB/CMR": "5022025", "Allocation": "", "MinimumSize": 12, 
         "Origin Pallet Number": "FP00058910", "Supplier": "BERRY PACKING SERVICES BV"},
        # Continue for all 151 rows...
    ]
    stock_df = pd.DataFrame(stock_data)
    orders = [
        {"customer_id": "C1", "fruit": "FIARGRN", "quantity": 200},  # Example order
        {"customer_id": "C2", "fruit": "FIARORG", "quantity": 300}
    ]
    restrictions = {
        "quality": ["Good Q/S", "Fair M/C"],
        "origin": ["Chile"],
        "variety": ["LEGACY"],
        "ggn": "4063061591012",
        "supplier": ["HORTIFRUT CHILE S.A."]
    }
    result = allocate_fruits(stock_df, orders, restrictions)
    print(result)
