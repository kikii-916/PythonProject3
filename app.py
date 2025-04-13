import os
from flask import Flask, render_template, request, url_for
import pandas as pd
import numpy as np

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False


def match_food_images(df):
    food_name_mapping = {
        '苹果': 'apple_pie',
        '鸡肉': 'chicken_curry',
        '披萨': 'pizza',
    }

    for index, row in df.iterrows():
        chinese_name = row['Food Names']

        english_name = food_name_mapping.get(chinese_name)

        if english_name:
            img_dir = os.path.join('food-101', 'images', english_name)
            if os.path.exists(img_dir):
                first_image = os.listdir(img_dir)[0]  # 取目录下的第一张图
                img_path = os.path.join(img_dir, first_image)

                df.at[index, 'Image'] = img_path.replace('\\', '/')  # Windows路径转Unix风格

    return df

def load_data():
    csv_path = os.path.join(os.path.dirname(__file__), 'cleaned_nutrition_dataset.csv')
    df = pd.read_csv(csv_path, encoding='utf-8')

    column_mapping = {
        'Caloric Value': 'Calories',
        'Protein': 'Protein',
        'Fat': 'Fat',
        'Carbohydrates': 'Carbohydrates',
        'food_normalized': 'Food Names',
        'Sodium': 'Sodium',
        'Dietary Fiber': 'Fiber',
        'Vitamin C': 'Vitamin_C',
        'Iron': 'Iron',
        'Calcium': 'Calcium',
        'Sugars': 'Sugars',
        'food': 'Original_Food_Name'
    }

    df = df.rename(columns={k: v for k, v in column_mapping.items() if k in df.columns})

    required_columns = ['Food Names', 'Calories', 'Protein', 'Fat', 'Carbohydrates']
    for col in required_columns:
        if col not in df.columns:
            raise ValueError(
                f"Required column '{col}' not found in dataset after mapping. Available columns: {df.columns.tolist()}")

    optional_columns = ['Sodium', 'Fiber', 'Vitamin_C', 'Iron', 'Calcium', 'Sugars']
    for col in optional_columns:
        if col not in df.columns:
            df[col] = 0

    numeric_cols = ['Calories', 'Protein', 'Fat', 'Carbohydrates', 'Sodium', 'Fiber', 'Iron', 'Calcium']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    return df


df = load_data()


def calculate_nutrition_score(food):
    score = 0

    protein = food.get('Protein', 0)
    if protein > 20:
        score += 30
    elif protein > 10:
        score += 20
    elif protein > 5:
        score += 10

    fiber = food.get('Fiber', 0)
    if fiber > 5:
        score += 20
    elif fiber > 3:
        score += 10
    elif fiber > 1:
        score += 5

    sodium = food.get('Sodium', 1000)
    if sodium < 300:
        score += 20
    elif sodium < 500:
        score += 10

    vitamin_c = food.get('Vitamin_C', 0)
    if vitamin_c > 10:
        score += 15
    elif vitamin_c > 5:
        score += 10

    minerals = (food.get('Iron', 0) + food.get('Calcium', 0)) / 2
    if minerals > 10:
        score += 15
    elif minerals > 5:
        score += 10

    return min(100, score)


def generate_tips(foods, target):
    tips = []
    avg_sodium = sum(f.get('Sodium', 0) for f in foods) / max(1, len(foods))
    avg_protein = sum(f.get('Protein', 0) for f in foods) / max(1, len(foods))
    avg_fiber = sum(f.get('Fiber', 0) for f in foods) / max(1, len(foods))

    if target == 'lose_fat':
        if avg_protein < 20:
            tips.append("Insufficient protein intake. It is recommended to supplement with high-quality proteins such as chicken breast and fish.")
        if avg_fiber < 5:
            tips.append("Inadequate dietary fiber intake. It is recommended to increase vegetables and whole grains.")
    elif target == 'hypertension':
        if avg_sodium > 300:
            tips.append(f"Current sodium intake is too high（{avg_sodium:.1f}mg）, it is recommended to choose low-sodium ingredients.")
    elif target == 'diabetes':
        if avg_fiber < 5:
            tips.append("nadequate intake of dietary fiber, which is beneficial for blood sugar stability.")

    if not tips:
        tips.append("Your diet plan is nutritionally balanced. Keep it up!")

    return tips

@app.route('/')
def cover():
    return render_template('cover.html')

@app.route('/home')
def home():
    return render_template('index.html')

@app.route('/plan', methods=['POST'])
def generate_plan():
    try:
        target = request.form['target']
        weight = float(request.form.get('weight', 60))
        height = float(request.form.get('height', 170))
        age = int(request.form.get('age', 25))
        gender = request.form.get('gender', 'male')
        preferences = request.form.getlist('preference')
        allergies = request.form.get('allergies', '')
        activity = request.form.get('activity', 'moderate')

        query_conditions = []

        if target == 'lose_fat':
            query_conditions.append((df['Calories'] < 300) & (df['Protein'] > 10))
        elif target == 'hypertension':
            query_conditions.append(df['Sodium'] < 300)
        elif target == 'diabetes':
            query_conditions.append((df['Fiber'] > 3) & (df['Carbohydrates'] < 30))
        elif target == 'gain_muscle':
            query_conditions.append((df['Protein'] > 15) & (df['Calories'] > 200))

        if 'vegetarian' in preferences:
            query_conditions.append(~df['Food Names'].str.contains('Meat|Fish|Shrimp|Crab|Shellfish|Chicken|Duck|Goose', na=False))
        if 'low_carb' in preferences:
            query_conditions.append(df['Carbohydrates'] < 20)
        if 'high_protein' in preferences:
            query_conditions.append(df['Protein'] > 15)
        if 'low_sodium' in preferences:
            query_conditions.append(df['Sodium'] < 200)

        if allergies:
            allergy_list = [a.strip() for a in allergies.split(',') if a.strip()]
            for allergen in allergy_list:
                query_conditions.append(~df['Food Names'].str.contains(allergen, case=False, na=False))

        if query_conditions:
            final_condition = query_conditions[0]
            for condition in query_conditions[1:]:
                final_condition &= condition
            filtered_df = df[final_condition]
        else:
            filtered_df = df

        if activity == 'sedentary':
            sample_size = 9
        elif activity == 'light':
            sample_size = 9
        elif activity == 'moderate':
            sample_size = 12
        elif activity == 'active':
            sample_size = 12
        else:  # extreme
            sample_size = 12

        foods = filtered_df.sample(min(sample_size, len(filtered_df))).to_dict('records')

        for food in foods:
            food['score'] = calculate_nutrition_score(food)
            food['id'] = str(hash(food['Food Names']))

        daily_needs = calculate_daily_needs(weight, height, age, gender, target, activity)

        total_calories = sum(f.get('Calories', 0) for f in foods)
        total_protein = sum(f.get('Protein', 0) for f in foods)
        protein_ratio = (total_protein * 4 / total_calories * 100) if total_calories > 0 else 0
        fiber_ratio = (
                    sum(f.get('Fiber', 0) for f in foods) / (total_calories / 1000) * 100) if total_calories > 0 else 0
        avg_sodium = sum(f.get('Sodium', 0) for f in foods) / max(1, len(foods))

        tips = generate_tips(foods, target)

        return render_template('result.html',
                               foods=foods,
                               target=target,
                               weight=weight,
                               height=height,
                               age=age,
                               gender=gender,
                               protein_ratio=round(protein_ratio, 1),
                               fiber_ratio=round(fiber_ratio, 1),
                               avg_sodium=round(avg_sodium, 1),
                               tips=tips,
                               daily_needs=daily_needs,
                               preferences=preferences,
                               allergies=allergies,
                               activity=activity)
    except Exception as e:
        return f"Error: {str(e)}", 400


def calculate_daily_needs(weight, height, age, gender, target, activity):
    if gender == 'female':
        bmr = 10 * weight + 6.25 * height - 5 * age - 161
    else:  # male
        bmr = 10 * weight + 6.25 * height - 5 * age + 5

    if activity == 'sedentary':
        activity_factor = 1.2
        protein_per_kg = 0.8
    elif activity == 'light':
        activity_factor = 1.375
        protein_per_kg = 1.0
    elif activity == 'moderate':
        activity_factor = 1.55
        protein_per_kg = 1.2
    elif activity == 'active':
        activity_factor = 1.725
        protein_per_kg = 1.5
    else:  # extreme
        activity_factor = 1.9
        protein_per_kg = 1.7

    tdee = bmr * activity_factor


    if target == 'lose_fat':
        calories = tdee * 0.8
        protein = weight * protein_per_kg
    elif target == 'gain_muscle':
        calories = tdee * 1.1
        protein = weight * (protein_per_kg + 0.3)
    elif target == 'hypertension':
        calories = tdee
        protein = weight * protein_per_kg
        sodium = 1500
    elif target == 'diabetes':
        calories = tdee * 0.9
        protein = weight * protein_per_kg
        carbs = calories * 0.4 / 4
    else:  # balanced
        calories = tdee
        protein = weight * protein_per_kg

    # 设置默认值
    needs = {
        'calories': round(calories),
        'protein': round(protein, 1),
        'carbs': round(calories * 0.5 / 4, 1),
        'fat': round(calories * 0.3 / 9, 1),
        'fiber': 25,
        'sodium': 2000,
        'bmr': round(bmr),
        'tdee': round(tdee)
    }

    if target == 'hypertension':
        needs['sodium'] = 1500

    return needs


@app.route('/foods', methods=['GET'])
def get_foods():
    try:
        search = request.args.get('search', '').strip()
        if search:
            mask = df['Food Names'].str.contains(search, case=False, na=False)
            filtered = df[mask].copy()
        else:
            filtered = df.copy()

        if search:
            filtered = filtered[filtered['Food Names'].str.contains(search, case=False, na=False)]

        foods = filtered.head(50).to_dict('records')
        for food in foods:
            food['id'] = str(hash(food['Food Names']))
            food['score'] = calculate_nutrition_score(food)

        return {'success': True, 'foods': foods}
    except Exception as e:
        return {'success': False, 'error': str(e)}



@app.route('/calculate', methods=['POST'])
def calculate_nutrition():
    try:
        food_ids = request.json.get('food_ids', [])
        selected_foods = []

        for food in df.to_dict('records'):
            if str(hash(food['Food Names'])) in food_ids:
                selected_foods.append(food)

        if not selected_foods:
            return {'success': False, 'error': 'No foods selected'}

        total = {
            'calories': sum(f.get('Calories', 0) for f in selected_foods),
            'protein': sum(f.get('Protein', 0) for f in selected_foods),
            'carbs': sum(f.get('Carbohydrates', 0) for f in selected_foods),
            'fat': sum(f.get('Fat', 0) for f in selected_foods),
            'fiber': sum(f.get('Fiber', 0) for f in selected_foods),
            'sodium': sum(f.get('Sodium', 0) for f in selected_foods)
        }

        return {'success': True, 'total': total}
    except Exception as e:
        return {'success': False, 'error': str(e)}


@app.route('/details/<food_name>')
def food_details(food_name):
    try:
        food = df[df['Food Names'].str.contains(food_name, case=False, na=False)].iloc[0].to_dict()
        food['score'] = calculate_nutrition_score(food)
        food['id'] = str(hash(food['Food Names']))
        return render_template('details.html', food=food)
    except Exception as e:
        return f"Food not found: {str(e)}", 404


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)

