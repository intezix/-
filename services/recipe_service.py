import json
from pathlib import Path
from typing import List, Optional, Dict, Set, Union
from dataclasses import dataclass
from config import RECIPES_PER_PAGE

@dataclass
class Ingredient:
    name: str
    amount: str
    grams: int

@dataclass
class Recipe:
    id: str
    name: str
    meal_type: str
    category_id: str
    tags: List[str]
    cooking_time: int
    calories: int
    proteins: float
    fats: float
    carbs: float
    ingredients: List[Ingredient]
    instructions: str
    image_url: str
    cooking_time_display: Optional[str] = None
    servings_display: Optional[str] = None
    calories_display: Optional[str] = None
    proteins_display: Optional[str] = None
    fats_display: Optional[str] = None
    carbs_display: Optional[str] = None
    instructions_ingredients: Optional[str] = None
    kbju_note: Optional[str] = None
    telegraph_url: Optional[str] = None
    telegraph_image_url: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> 'Recipe':
        ingredients = [Ingredient(name=ing['name'], amount=ing['amount'], grams=ing['grams']) for ing in data.get('ingredients', [])]
        return cls(id=data['id'], name=data['name'], meal_type=data['meal_type'], category_id=data['category_id'], tags=data.get('tags', []), cooking_time=data['cooking_time'], calories=data['calories'], proteins=data['proteins'], fats=data['fats'], carbs=data['carbs'], ingredients=ingredients, instructions=data['instructions'], image_url=data['image_url'], cooking_time_display=data.get('cooking_time_display'), servings_display=data.get('servings_display'), calories_display=data.get('calories_display'), proteins_display=data.get('proteins_display'), fats_display=data.get('fats_display'), carbs_display=data.get('carbs_display'), instructions_ingredients=data.get('instructions_ingredients'), kbju_note=data.get('kbju_note'), telegraph_url=data.get('telegraph_url'), telegraph_image_url=data.get('telegraph_image_url'))

    def format_ingredients(self) -> str:
        lines = []
        for ing in self.ingredients:
            lines.append(f'• {ing.name} — {ing.amount} ({ing.grams} г)')
        return '\n'.join(lines)

    def format_nutrition(self) -> str:
        return f'🔥 Калории: {self.calories} ккал\n🥩 Белки: {self.proteins} г\n🧈 Жиры: {self.fats} г\n🍞 Углеводы: {self.carbs} г'

    def format_full(self) -> str:
        return f'🍽 <b>{self.name}</b>\n\n⏱ Время приготовления: {self.cooking_time} мин\n\n<b>📝 Ингредиенты:</b>\n{self.format_ingredients()}\n\n<b>👨\u200d🍳 Приготовление:</b>\n{self.instructions}\n\n<b>📊 КБЖУ:</b>\n{self.format_nutrition()}'

    def format_short(self) -> str:
        return f'<b>{self.name.upper()}</b>\n⏱ {self.cooking_time} мин  •  🔥 {self.calories} ккал'

    def format_for_telegraph(self) -> str:
        image_html = ''
        if self.image_url and str(self.image_url).strip().startswith('https://'):
            image_html = f'<img src="{self.image_url}" alt="">'
        cal = self.calories_display if self.calories_display else str(self.calories)
        prot = self.proteins_display if self.proteins_display else str(self.proteins).replace('.', ',')
        fat = self.fats_display if self.fats_display else str(self.fats).replace('.', ',')
        carb = self.carbs_display if self.carbs_display else str(self.carbs).replace('.', ',')
        time_str = self.cooking_time_display if self.cooking_time_display else f'{self.cooking_time} минут'
        servings = self.servings_display if self.servings_display else '1'
        if self.instructions_ingredients:
            ing_lines = self.instructions_ingredients.split('\n')
            ingredients_html = ''
            current_list = None
            for line in ing_lines:
                line_stripped = line.strip()
                if not line_stripped:
                    continue
                is_section_header = line_stripped.endswith(':') and '—' not in line_stripped or line_stripped.startswith('Для ')
                if is_section_header:
                    if current_list is not None:
                        ingredients_html += '</ul>'
                        current_list = None
                    header_text = line_stripped.replace('<b>', '').replace('</b>', '').strip()
                    ingredients_html += f'<p><b>{header_text}</b></p>'
                else:
                    if current_list is None:
                        ingredients_html += '<ul>'
                        current_list = True
                    clean_line = line_stripped.lstrip('·•● ').strip()
                    clean_line = clean_line.replace('<b>', '').replace('</b>', '').strip()
                    if clean_line:
                        ingredients_html += f'<li>{clean_line}</li>'
            if current_list is not None:
                ingredients_html += '</ul>'
        else:
            ingredients_html = '<ul>' + ''.join([f'<li>{ing.name} — {ing.amount}</li>' for ing in self.ingredients]) + '</ul>'
        instructions_lines = self.instructions.split('\n')
        instructions_html = ''
        for line in instructions_lines:
            if line.strip():
                if line.endswith(':') and (not line[0].isdigit()):
                    instructions_html += f'<p><b>{line}</b></p>'
                else:
                    instructions_html += f'<p>{line}</p>'
        kbju_title = '📊 КБЖУ'
        if self.kbju_note:
            kbju_title += f' {self.kbju_note}'
        protection_style = 'style="user-select: none; -webkit-user-select: none; -moz-user-select: none; -ms-user-select: none; -webkit-touch-callout: none;"'
        return f'{image_html}<!--noai-->\n<!--noindex-->\n<!--nofollow-->\n<p {protection_style}><i>⏱ Время приготовления: {time_str}</i><br><i>🍽 Порция: {servings}</i></p><hr><h4 {protection_style}>🛒 Ингредиенты</h4><div {protection_style}>{ingredients_html}</div><hr><h4 {protection_style}>👩🏽\u200d🍳 Приготовление</h4><div {protection_style}>{instructions_html}</div><hr><blockquote {protection_style}><b>{kbju_title}</b><br><br>🔥 Калории: <b>{cal}</b> ккал<br>🥚 Белки: <b>{prot}</b> г<br>🧈 Жиры: <b>{fat}</b> г<br>🍞 Углеводы: <b>{carb}</b> г</blockquote>'

@dataclass
class Category:
    id: str
    name: str
    description: str

class RecipeService:
    _instance: Optional['RecipeService'] = None
    _recipes: List[Recipe] = []
    _categories: Dict[str, List[Category]] = {}

    def __new__(cls) -> 'RecipeService':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_data()
        return cls._instance

    def _load_data(self) -> None:
        base_path = Path(__file__).parent.parent / 'data'
        recipes_path = base_path / 'recipes.json'
        with open(recipes_path, 'r', encoding='utf-8') as f:
            recipes_data = json.load(f)
        self._recipes = [Recipe.from_dict(r) for r in recipes_data.get('recipes', [])]
        lunch_dinner_path = base_path / 'recipes_lunch_dinner.json'
        if lunch_dinner_path.exists():
            with open(lunch_dinner_path, 'r', encoding='utf-8') as f:
                ld_data = json.load(f)
            existing_ids = {r.id for r in self._recipes}
            for r in ld_data.get('recipes', []):
                if r.get('id') not in existing_ids:
                    self._recipes.append(Recipe.from_dict(r))
        categories_path = base_path / 'categories.json'
        with open(categories_path, 'r', encoding='utf-8') as f:
            categories_data = json.load(f)
        self._categories = {}
        for meal_type, cats in categories_data.items():
            self._categories[meal_type] = [Category(id=c['id'], name=c['name'], description=c['description']) for c in cats]

    def get_categories(self, meal_type: str) -> List[Category]:
        return self._categories.get(meal_type, [])

    def _meal_matches(self, recipe_meal_type: str, selected_meal_type: str) -> bool:
        if recipe_meal_type == selected_meal_type:
            return True
        if recipe_meal_type == 'lunch_dinner' and selected_meal_type in ('lunch', 'dinner'):
            return True
        return False

    def get_recipes_by_category(self, meal_type: str, category_id: str) -> List[Recipe]:
        return [r for r in self._recipes if r.category_id == category_id and self._meal_matches(r.meal_type, meal_type)]

    def get_recipes_by_filters(self, meal_type: str, filter_tags: Set[str]) -> List[Recipe]:
        matching_meal = [r for r in self._recipes if self._meal_matches(r.meal_type, meal_type)]
        if not filter_tags:
            return matching_meal
        if meal_type in ('lunch', 'dinner'):
            ld_filter_tags = {'quick_25', 'oven', 'hearty', 'light', 'protein', 'balanced'}
            if filter_tags == {'hearty'}:
                allowed_variants = [{'hearty'}, {'hearty', 'quick_25'}, {'hearty', 'oven'}]
                result: list[Recipe] = []
                for r in matching_meal:
                    recipe_ld_tags = set(r.tags) & ld_filter_tags
                    if recipe_ld_tags in allowed_variants:
                        result.append(r)
                return result
            if filter_tags == {'light'}:
                allowed_variants = [{'light'}, {'light', 'quick_25'}]
                result: list[Recipe] = []
                for r in matching_meal:
                    recipe_ld_tags = set(r.tags) & ld_filter_tags
                    if recipe_ld_tags in allowed_variants:
                        result.append(r)
                return result
        return [r for r in matching_meal if filter_tags.issubset(set(r.tags))]

    def is_filter_available(self, meal_type: str, selected_filters: Set[str], new_filter_tag: str) -> bool:
        if meal_type not in ('lunch', 'dinner'):
            return True
        if new_filter_tag in selected_filters:
            return True
        test_filters = selected_filters | {new_filter_tag}
        recipes = self.get_recipes_by_filters(meal_type, test_filters)
        return len(recipes) > 0

    def get_recipe_by_id(self, recipe_id: str) -> Optional[Recipe]:
        for recipe in self._recipes:
            if recipe.id == recipe_id:
                return recipe
        return None

    def paginate(self, recipes: List[Recipe], page: int) -> tuple[List[Recipe], int, bool, bool]:
        total = len(recipes)
        start = page * RECIPES_PER_PAGE
        end = start + RECIPES_PER_PAGE
        page_recipes = recipes[start:end]
        has_prev = page > 0
        has_next = end < total
        return (page_recipes, total, has_prev, has_next)

    def get_total_pages(self, recipes: List[Recipe]) -> int:
        total = len(recipes)
        return (total + RECIPES_PER_PAGE - 1) // RECIPES_PER_PAGE