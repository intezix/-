import json
from pathlib import Path
STUB_RECIPE = {'cooking_time': 25, 'calories': 350, 'proteins': 25, 'fats': 12, 'carbs': 30, 'ingredients': [{'name': '—', 'amount': '—', 'grams': 0}], 'instructions': 'Рецепт скоро будет добавлен.', 'image_url': ''}
MEAT_POULTRY = ['Куриная грудка с булгуром', 'Курица с брокколи в йогуртовом соусе', 'Стейки индейки с гречкой', 'Куриные бедра с рисом', 'Рубленые котлетки с кус кусом', 'Макароны с куриной грудкой', 'Запеканка из куриного филе', 'Хрустящие пп рулетики из курицы', 'Запечённая курица с картофелем и зеленью', 'Куриные тефтели с гречкой', 'Тушёная говядина с овощами', 'Котлеты из говядины с булгуром', 'Куриная запеканка с брокколи', 'Говядина с овощами и макаронами', 'Куриная грудка с овощами на сковороде', 'Говядина с зеленой фасолью', 'Плов с говядиной', 'Батат с куриным фаршем', 'Рис с овощами и куриным фаршем', 'Стейки говядины с рисом']
FISH_SEAFOOD = ['Лосось с бурым рисом', 'Треска с овощным рагу', 'Лосось с киноа и овощами', 'Поке с креветками', 'Горбуша в сливочном соусе', 'Морепродукты с рисом', 'Кальмар с овощами', 'Белая рыба с рисом и брокколи', 'Форель в йогуртово горчичном соусе с киноа']
PASTA_NOODLES = ['Лосось с кабачковой лапшой', 'ПП-паста с курицей', 'Паста с лососем и брокколи', 'Гречневая лапша с мидиями', 'Рисовая лапша с креветками и овощами', 'Паста с курицей и песто', 'Паста с тунцом и томатами', 'Гречневая лапша с лососем', 'Паста с курицей и грибами']
SALADS_LUNCH = ['Салат с курицей, авокадо и зеленью', 'Салат с тунцом высокобелковый', 'Куриный салат с грибами и морковью', 'Цезарь с курицей ПП', 'Салат с курицей и киноа', 'Салат с копченой индейкой', 'ПП крабовый салат']
SALADS_LIGHT = ['Греческий салат', 'Салат с яйцом и овощами', 'Салат с кальмаром', 'Цезарь с креветками ПП', 'Салат с ветчиной из индейки', 'Салат с форелью', 'Салат Коул-Слоу', 'Салат с моцареллой и зеленью']
PP_FASTFOOD = ['ПП пицца', 'Шаурма с курицей', 'Ролл с лососем и авокадо', 'Бургер с курицей', 'Бургер с говядиной', 'ПП-наггетсы из курицы', 'Батат фри в духовке', 'Кабачковые палочки в духовке', 'Куриные стрипсы в духовке']

def slug(s: str) -> str:
    return s.lower().replace(' ', '_').replace('-', '_').replace(',', '').replace("'", '').replace('ё', 'е')[:50]

def build_recipe(recipe_id: str, name: str, meal_type: str, category_id: str) -> dict:
    r = dict(STUB_RECIPE)
    r['id'] = recipe_id
    r['name'] = name
    r['meal_type'] = meal_type
    r['category_id'] = category_id
    r['tags'] = []
    return r

def main():
    base = Path(__file__).parent
    path = base / 'recipes.json'
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    recipes = data['recipes']
    existing_ids = {r['id'] for r in recipes}
    new_recipes = []
    for i, name in enumerate(MEAT_POULTRY, 1):
        rid = f'ld_meat_{i}'
        if rid not in existing_ids:
            new_recipes.append(build_recipe(rid, name, 'lunch_dinner', 'meat_poultry'))
    for i, name in enumerate(FISH_SEAFOOD, 1):
        rid = f'ld_fish_{i}'
        if rid not in existing_ids:
            new_recipes.append(build_recipe(rid, name, 'lunch_dinner', 'fish_seafood'))
    for i, name in enumerate(PASTA_NOODLES, 1):
        rid = f'lunch_pasta_{i}'
        if rid not in existing_ids:
            new_recipes.append(build_recipe(rid, name, 'lunch', 'pasta_noodles'))
    for i, name in enumerate(SALADS_LUNCH, 1):
        rid = f'lunch_salad_{i}'
        if rid not in existing_ids:
            new_recipes.append(build_recipe(rid, name, 'lunch', 'salads'))
    for i, name in enumerate(SALADS_LIGHT, 1):
        rid = f'dinner_salad_{i}'
        if rid not in existing_ids:
            new_recipes.append(build_recipe(rid, name, 'dinner', 'salads_light'))
    for i, name in enumerate(PP_FASTFOOD, 1):
        rid = f'dinner_fastfood_{i}'
        if rid not in existing_ids:
            new_recipes.append(build_recipe(rid, name, 'dinner', 'pp_fastfood'))
    if not new_recipes:
        print('Все рецепты уже есть в recipes.json.')
        return
    data['recipes'] = recipes + new_recipes
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f'Добавлено рецептов: {len(new_recipes)}')
if __name__ == '__main__':
    main()