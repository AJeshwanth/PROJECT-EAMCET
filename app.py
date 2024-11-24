from flask import Flask, jsonify, render_template, request, redirect
from pymongo import MongoClient
from flask_cors import CORS
import pandas as pd
app = Flask(__name__)
CORS(app)  # Enable CORS for frontend access

# MongoDB Configuration
client = MongoClient("mongodb+srv://<username>:DS31otkg2TlGy0NZ@<cluster-url>/myDatabase?retryWrites=true&w=majority")
db = client["EAMCET"]  # Replace with your database name
colleges_collection = db["EAMCET2023"]  # Replace with your collection name
@app.route('/')
def home():
    # Render the HTML page
    data = colleges_collection.find_one({'name': 'EAMCET'})
    colleges = [
        {
            'id': i,
            'name': college['college_name'],
            'value': college['college_name']  # Extract the last 4 letters
        }
        for i, college in enumerate(data.get('colleges', []))
    ]
    return render_template('Homepage.html', colleges=colleges)
@app.route('/predict')
def predict():
    return render_template('predictor.html')
@app.route('/about')
def about():
    return render_template('about.html')
@app.route('/search', methods=['GET'])
def search():
    query = request.args.get('query', '').lower()  # Get the query parameter from the URL
    print(query)  # This will help in debugging; you can remove it later

    if query == 'about':
        return redirect('/about')
    elif query == 'predictor':
        return redirect('/predict')
    elif query == 'home':
        return redirect('/')
    else:
        # If no match, render the not_found page and pass the query to display it
        return render_template('not_found.html', query=query)
@app.route('/get-branches', methods=['POST'])
def get_branches():
    college_id = request.json.get("college_id")
    print(college_id)  # Log the college_id for debugging purposes
    
    try:
        # Query to find the college by name 'EAMCET'
        data = colleges_collection.find_one({'name': 'EAMCET'})

        # Check if the 'colleges' field exists in the data
        if data and 'colleges' in data:
            # Iterate over the colleges to find the one that matches the last 6 characters of the college_name
            for college in data['colleges']:
                if college['college_name'] == college_id:
                    # Extract the branches for the matched college
                    branches = [{"branch_name": branch["branch_name"]} for branch in college["branches"]]
                    
                    # Return the branches as a JSON response
                    return jsonify({"branches": branches})

        # If no college found with the matching college_id
        return jsonify({"branches": []}), 404

    except Exception as e:
        # Handle any errors that occur
        return jsonify({"error": str(e)}), 500
@app.route('/search-students', methods=['POST'])
def search_students():
    try:
        # Get the data from the request (college_id, branch, year)
        college_name = request.json.get("college")
        branch_name = request.json.get("branch")
        year = request.json.get("year")
        student_name = request.json.get("name")
        print(f"EAMCET{year}")
        colleges_collection=db[f"EAMCET{year}"]
        # Query to find the college by name 'EAMCET'
        match_query = {}
# Dynamically add filters to match_query
        if student_name.strip():  # Add only if student_name is not empty or whitespace
            match_query["colleges.branches.students.candidate_name"] = {
                "$regex": student_name,
                "$options": "i"  # Case-insensitive search
            }

        if college_name.strip():  # Add only if college_name is not empty or whitespace
            match_query["colleges.college_name"] = college_name

        if branch_name.strip():  # Add only if branch_name is not empty or whitespace
            match_query["colleges.branches.branch_name"] = branch_name
        print(match_query)
        # Aggregation Pipeline
        pipeline = [
            { "$unwind": "$colleges" },
            { "$unwind": "$colleges.branches" },
            { "$unwind": "$colleges.branches.students" },
            { "$match": match_query },  # Apply the dynamic match query
            {
                "$project": {  # Select fields to include in the result
                    "_id": 0,
                    "college": "$colleges.college_name",
                    "branch": "$colleges.branches.branch_name",
                    "candidate_name": "$colleges.branches.students.candidate_name",
                    "rank": "$colleges.branches.students.rank",
                    "gender": "$colleges.branches.students.gender",
                    "region": "$colleges.branches.students.region",
                    "category": "$colleges.branches.students.category",
                    "seat_category": "$colleges.branches.students.seat_category"
                }
            }
        ]

        # Execute the query
        results = list(colleges_collection.aggregate(pipeline))
        print("Results not found")
        # Return the list of students as a JSON response
        if results:
            i=1
            for student in results:
                student["id"]=i
                i+=1
            print(results)
            return jsonify({"Results" : len(results), "students": results})
        
        return jsonify({"students": []}), 404  # No students found

    except Exception as e:
        # Handle any errors that occur
        return jsonify({"error": str(e)}), 500
@app.route('/predict-college', methods=['POST'])
def predict_college():
    file_path = "cuttoff.xlsx"
    colgname = "INSTITUTE NAME"
    
    # Get values from the request
    rank = request.json.get("rank")
    gender = request.json.get("gender")
    category = request.json.get("category")
    branch = request.json.get("branch")

    # Validate inputs
    if not rank or not gender or not category or not branch:
        return jsonify({"message": "All fields (rank, gender, category, branch) are required."}), 400
    
    # Concatenate category with gender
    category = category + " " + gender

    response = {"colleges": []}  # To store the result
    
    try:
        # Load the Excel data
        df = pd.read_excel(file_path, header=1)
        
        # Check if the necessary columns exist in the dataframe
        if colgname in df.columns and category in df.columns and "BRANCH" in df.columns:
            # Drop rows with NaN values
            extracted_data = df[[colgname, category, "BRANCH"]].dropna()

            # Filter data by the selected branch
            filtered_data = extracted_data[extracted_data["BRANCH"] == branch]
            # print(filtered_data)
            if not filtered_data.empty:
    # Create a dictionary of college names and their cutoff ranks
                colg_dict = dict(zip(filtered_data[colgname], filtered_data[category]))

                # Sort by cutoff rank (ensure cutoff rank is an integer for sorting)
                try:
                    scolg_dict = dict(sorted(colg_dict.items(), key=lambda item: item[1]))
                except ValueError:
                    response["message"] = "Error: Invalid cutoff rank value found."
                    return jsonify(response)

                # Find the ceiling rank
                ceiling_rank = None
                for college, cutoff_rank in scolg_dict.items():
                    try:
                        # Ensure cutoff_rank is an integer
                        cutoff_rank = int(cutoff_rank)
                        if cutoff_rank >= int(rank):
                            ceiling_rank = cutoff_rank
                            break
                    except ValueError:
                        continue

                # Collect colleges based on the ceiling rank
                if ceiling_rank is not None:
                    count = 0
                    for college, cutoff_rank in scolg_dict.items():
                        try:
                            cutoff_rank = int(cutoff_rank)
                            if cutoff_rank >= ceiling_rank:
                                response["colleges"].append({
                                    "college_name": college,
                                    "cutoff_rank": cutoff_rank,  # Ensure integer for cutoff rank
                                    "branch": branch,
                                    "category": category
                                })
                                count += 1
                                if count >= 10:
                                    break
                        except ValueError:
                            continue
                else:
                    # If no ceiling rank found, return the last 5 colleges
                    last_5_colleges = list(scolg_dict.items())[-5:]
                    for college, cutoff_rank in last_5_colleges:
                        try:
                            cutoff_rank = int(cutoff_rank)
                            response["colleges"].append({
                                "college_name": college,
                                "cutoff_rank": cutoff_rank,  # Ensure integer for cutoff rank
                                "branch": branch,
                                "category": category
                            })
                        except ValueError:
                            continue
            else:
                response["message"] = "No data found matching the criteria."


        else:
            response["message"] = f"One or more specified columns ('{colgname}', '{category}', 'BRANCH') not found in the Excel file."
    
    except Exception as e:
        response["message"] = f"Error reading the Excel file: {e}"

    print(response)
    return jsonify(response)

if __name__ == '__main__':
    app.run(debug=True)
