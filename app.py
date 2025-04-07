import os
from flask import Flask, render_template, request, url_for
import pandas as pd
import numpy as np

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False

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

    sodium = food.get('Sodium', 1000)  # 默认假设高钠
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
            tips.append("蛋白质摄入不足，建议补充优质蛋白如鸡胸肉、鱼类")
        if avg_fiber < 5:
            tips.append("膳食纤维摄入不足，建议增加蔬菜和全谷物")
    elif target == 'hypertension':
        if avg_sodium > 300:
            tips.append(f"当前钠摄入量偏高（{avg_sodium:.1f}mg），建议选择低钠食材")
    elif target == 'diabetes':
        if avg_fiber < 5:
            tips.append("膳食纤维摄入不足，有助于血糖稳定")

    if not tips:
        tips.append("您的饮食计划营养均衡，继续保持！")

    return tips


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/plan', methods=['POST'])
def generate_plan():
    try:
        target = request.form['target']
        weight = float(request.form.get('weight', 70))  # 默认70kg

        if target == 'lose_fat':
            # 减脂：低热量高蛋白
            foods = df[(df['Calories'] < 300) & (df['Protein'] > 10)].sample(5).to_dict('records')
        elif target == 'hypertension':
            # 高血压：低钠高钾
            foods = df[df['Sodium'] < 300].sample(5).to_dict('records')
        elif target == 'diabetes':
            # 糖尿病：高纤维低碳水
            foods = df[(df['Fiber'] > 3) & (df['Carbohydrates'] < 30)].sample(5).to_dict('records')
        else:
            foods = df.sample(5).to_dict('records')

        # 计算营养评分
        for food in foods:
            food['score'] = calculate_nutrition_score(food)

        # 计算整体指标
        total_calories = sum(f.get('Calories', 0) for f in foods)
        total_protein = sum(f.get('Protein', 0) for f in foods)
        protein_ratio = (total_protein * 4 / total_calories * 100) if total_calories > 0 else 0
        fiber_ratio = (
                    sum(f.get('Fiber', 0) for f in foods) / (total_calories / 1000) * 100) if total_calories > 0 else 0
        avg_sodium = sum(f.get('Sodium', 0) for f in foods) / max(1, len(foods))

        # 生成健康小贴士
        tips = generate_tips(foods, target)

        return render_template('result.html',
                               foods=foods,
                               target=target,
                               weight=weight,
                               protein_ratio=round(protein_ratio, 1),
                               fiber_ratio=round(fiber_ratio, 1),
                               avg_sodium=round(avg_sodium, 1),
                               tips=tips)
    except Exception as e:
        return f"Error: {str(e)}", 400


@app.route('/details/<food_name>')
def food_details(food_name):
    try:
        food = df[df['Food Names'].str.contains(food_name, case=False, na=False)].iloc[0].to_dict()

        food['score'] = calculate_nutrition_score(food)

        return render_template('details.html', food=food)
    except Exception as e:
        return f"Food not found: {str(e)}", 404


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
