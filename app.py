import os
from flask import Flask, render_template, request, url_for
import pandas as pd
import numpy as np

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False


def match_food_images(df):
    """将食物名称与Food-101数据集中的图片匹配"""
    # 示例：将中文食物名映射到Food-101的英文类别
    food_name_mapping = {
        '苹果': 'apple_pie',  # 示例映射（需根据你的食物列表补充）
        '鸡肉': 'chicken_curry',
        '披萨': 'pizza',
        # 添加更多映射...
    }

    for index, row in df.iterrows():
        chinese_name = row['Food Names']

        # 1. 通过映射表获取对应的英文类别名
        english_name = food_name_mapping.get(chinese_name)

        if english_name:
            # 2. 构建图片路径（取对应类别的第一张图片）
            img_dir = os.path.join('food-101', 'images', english_name)
            if os.path.exists(img_dir):
                first_image = os.listdir(img_dir)[0]  # 取目录下的第一张图
                img_path = os.path.join(img_dir, first_image)

                # 3. 将相对路径转换为Web可访问路径
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


# ... (前面的import和load_data等函数保持不变)

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

        # 根据目标和偏好筛选食物
        query_conditions = []

        if target == 'lose_fat':
            query_conditions.append((df['Calories'] < 300) & (df['Protein'] > 10))
        elif target == 'hypertension':
            query_conditions.append(df['Sodium'] < 300)
        elif target == 'diabetes':
            query_conditions.append((df['Fiber'] > 3) & (df['Carbohydrates'] < 30))
        elif target == 'gain_muscle':
            query_conditions.append((df['Protein'] > 15) & (df['Calories'] > 200))

        # 处理饮食偏好
        if 'vegetarian' in preferences:
            query_conditions.append(~df['Food Names'].str.contains('肉|鱼|虾|蟹|贝|鸡|鸭|鹅', na=False))
        if 'low_carb' in preferences:
            query_conditions.append(df['Carbohydrates'] < 20)
        if 'high_protein' in preferences:
            query_conditions.append(df['Protein'] > 15)
        if 'low_sodium' in preferences:
            query_conditions.append(df['Sodium'] < 200)

        # 处理过敏原
        if allergies:
            allergy_list = [a.strip() for a in allergies.split(',') if a.strip()]
            for allergen in allergy_list:
                query_conditions.append(~df['Food Names'].str.contains(allergen, case=False, na=False))

        # 合并所有查询条件
        if query_conditions:
            final_condition = query_conditions[0]
            for condition in query_conditions[1:]:
                final_condition &= condition
            filtered_df = df[final_condition]
        else:
            filtered_df = df

        # 根据活动量调整推荐数量
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

        # 计算营养评分
        for food in foods:
            food['score'] = calculate_nutrition_score(food)
            food['id'] = str(hash(food['Food Names']))  # 为每个食物生成唯一ID用于前端拖拽

        # 计算每日营养需求
        daily_needs = calculate_daily_needs(weight, height, age, gender, target, activity)

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
    # 基础代谢率 (Mifflin-St Jeor 公式)
    if gender == 'female':
        bmr = 10 * weight + 6.25 * height - 5 * age - 161
    else:  # male
        bmr = 10 * weight + 6.25 * height - 5 * age + 5

    # 活动系数
    if activity == 'sedentary':
        activity_factor = 1.2
        protein_per_kg = 0.8  # 久坐少动: 0.8g/kg
    elif activity == 'light':
        activity_factor = 1.375
        protein_per_kg = 1.0  # 轻度活动: 1.0g/kg
    elif activity == 'moderate':
        activity_factor = 1.55
        protein_per_kg = 1.2  # 中度活动: 1.2g/kg
    elif activity == 'active':
        activity_factor = 1.725
        protein_per_kg = 1.5  # 高度活跃: 1.5g/kg
    else:  # extreme
        activity_factor = 1.9
        protein_per_kg = 1.7  # 极高强度: 1.7g/kg

    tdee = bmr * activity_factor

    # 根据目标调整
    if target == 'lose_fat':
        calories = tdee * 0.8
        protein = weight * protein_per_kg
    elif target == 'gain_muscle':
        calories = tdee * 1.1
        protein = weight * (protein_per_kg + 0.3)  # 增肌比常规多0.3g/kg
    elif target == 'hypertension':
        calories = tdee
        protein = weight * protein_per_kg
        sodium = 1500  # 高血压患者建议更低
    elif target == 'diabetes':
        calories = tdee * 0.9
        protein = weight * protein_per_kg
        carbs = calories * 0.4 / 4  # 40%热量来自碳水
    else:  # balanced
        calories = tdee
        protein = weight * protein_per_kg

    # 设置默认值
    needs = {
        'calories': round(calories),
        'protein': round(protein, 1),
        'carbs': round(calories * 0.5 / 4, 1),  # 50%热量来自碳水
        'fat': round(calories * 0.3 / 9, 1),  # 30%热量来自脂肪
        'fiber': 25,  # 固定25g膳食纤维
        'sodium': 2000,  # 钠摄入量限制2000mg
        'bmr': round(bmr),  # 添加BMR显示
        'tdee': round(tdee)  # 添加TDEE显示
    }

    # 特殊目标调整
    if target == 'hypertension':
        needs['sodium'] = 1500  # 高血压患者建议更低

    return needs


@app.route('/foods', methods=['GET'])
def get_foods():
    try:
        search = request.args.get('search', '').strip()
        # 使用更高效的搜索方法
        if search:
            mask = df['Food Names'].str.contains(search, case=False, na=False)
            filtered = df[mask].copy()
        else:
            filtered = df.copy()

        # 搜索筛选
        if search:
            filtered = filtered[filtered['Food Names'].str.contains(search, case=False, na=False)]

        # 转换为字典并添加ID
        foods = filtered.head(50).to_dict('records')
        for food in foods:
            food['id'] = str(hash(food['Food Names']))
            food['score'] = calculate_nutrition_score(food)

        return {'success': True, 'foods': foods}
    except Exception as e:
        return {'success': False, 'error': str(e)}



@app.route('/calculate', methods=['POST'])
def calculate_nutrition():
    """计算一组食物的总营养值"""
    try:
        food_ids = request.json.get('food_ids', [])
        selected_foods = []

        # 在实际应用中，这里应该从数据库查询，这里简化为遍历
        for food in df.to_dict('records'):
            if str(hash(food['Food Names'])) in food_ids:
                selected_foods.append(food)

        if not selected_foods:
            return {'success': False, 'error': 'No foods selected'}

        # 计算总和
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

