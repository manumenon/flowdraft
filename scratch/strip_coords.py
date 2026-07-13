import json

with open("assets/default-spec-v2.json", "r", encoding="utf-8") as f:
    spec = json.load(f)

def clean_element(elem):
    elem.pop("x", None)
    elem.pop("y", None)
    if "children" in elem:
        for child in elem["children"]:
            clean_element(child)
    if "footer" in elem:
        clean_element(elem["footer"])

for elem in spec.get("elements", []):
    clean_element(elem)

# Let's make sure input_panel layout has direction "column"
for elem in spec.get("elements", []):
    if elem.get("id") == "input_panel":
        elem["layout"]["direction"] = "column"

with open("outputs/default-spec-v2-auto.json", "w", encoding="utf-8") as f:
    json.dump(spec, f, indent=2)

print("Coordinates stripped successfully.")
