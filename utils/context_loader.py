import os

def load_engineering_standards() -> str:
    # Use absolute path based on the project root to avoid working directory issues
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    rules_dir = os.path.join(base_dir, "rules")
    
    combined_rules = []
    
    if not os.path.exists(rules_dir):
         return "No internal standards provided."
         
    for filename in os.listdir(rules_dir):
        if filename.endswith(".md"):
            with open(os.path.join(rules_dir, filename), "r", encoding="utf-8") as f:
                combined_rules.append(f"--- {filename} ---\n{f.read()}")
                
    return "\n\n".join(combined_rules)
