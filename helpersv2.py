import json
import pandas as pd

# Split a chatbot response into text and graphs
def split_response(response):
    start_index = response.find('```json\n')
    if start_index != -1:
        start_index += len('```json\n')
        # Extract text and json data
        text = response[:response.find('```json\n')].strip()
        json_data = response[start_index:].split('```')[0].strip()
        try:
            # Load the JSON data
            data = json.loads(json_data)
            graphs = []
            for graph in data["charts"]:
                # Create graph based on the data
                graphs.append((data["charts"][graph], extract_table_from_graph(data["charts"][graph])))
            return text, graphs
        except json.JSONDecodeError:
            return text, None
    else:
        # If no graphs, return text only
        return response, None

def format_number(num):
    if pd.isna(num):
        return "-"
    abs_num = abs(num)
    if abs_num >= 1_000_000:
        return f"{num / 1_000_000:.1f}M"
    elif abs_num >= 1_000:
        return f"{num / 1_000:.0f}K"
    else:
        return f"{num:.0f}"

def extract_table_from_graph(graph):
    chart_type = graph.get("chart", {}).get("type")
    # Handle Pie Chart format
    if chart_type == "pie":
        data = graph.get("series", [{}])[0].get("data", [])
        categories = [d.get("name") for d in data]
        values = [d.get("y") for d in data]

        df = pd.DataFrame({graph.get("series", [{}])[0].get("name"): values}, index=categories)
        df.index.name = "Category"
    else:
        categories = graph.get("xAxis", {}).get("categories", [])
        data_dict = {}
        for series in graph.get("series", []):
            data_dict[series["name"]] = series.get("data", [])

        try:
            # Attempt to create the DataFrame with the categories as the index
            df = pd.DataFrame(data_dict, index=categories)
            df.index.name = graph.get("xAxis", {}).get("title", {}).get("text", "Category")
        except ValueError as e:
            # If a ValueError occurs (due to mismatched lengths), create the DataFrame without an index
            print(f"Caught ValueError: {e}. Creating DataFrame without index.")
            all_lengths = [len(d) for d in data_dict.values()]
            max_len = max(all_lengths) if all_lengths else 0

            for key in data_dict:
                data_list = data_dict[key]
                while len(data_list) < max_len:
                    data_list.append(None)
            df = pd.DataFrame(data_dict)

    return df.map(format_number)
