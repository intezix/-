from aiogram.fsm.state import State, StatesGroup
from dataclasses import dataclass, field
from typing import Optional, Set, Literal, List


class UserState(StatesGroup):
    welcome = State()
    welcome_step1 = State()
    welcome_step2 = State()
    welcome_step3 = State()
    choosing_meal = State()
    browsing_categories = State()
    choosing_filters = State()
    browsing_recipes = State()
    selecting_favourites = State()
    viewing_recipe = State()
    recipe_accepted = State()


class BillingState(StatesGroup):
    waiting_email = State()


@dataclass
class UserContext:
    meal_type: Optional[str] = None
    category_id: Optional[str] = None
    selected_filters: Set[str] = field(default_factory=set)
    page: int = 0
    source: Literal["category", "filters", "favourites"] = "category"
    current_recipe_id: Optional[str] = None
    message_ids: List[int] = field(default_factory=list)
    selected_recipe_ids: Set[str] = field(default_factory=set)
    selection_context: Optional[str] = None
    page_recipe_ids: List[str] = field(default_factory=list)
    favourites_list_message_id: Optional[int] = None
    recipes_list_message_ids: List[int] = field(default_factory=list)

    def clear_messages(self) -> None:
        self.message_ids = []

    def add_message(self, message_id: int) -> None:
        self.message_ids.append(message_id)

    def reset_filters(self) -> None:
        self.selected_filters = set()

    def toggle_filter(self, filter_tag: str) -> None:
        if filter_tag in self.selected_filters:
            self.selected_filters.discard(filter_tag)
        else:
            self.selected_filters.add(filter_tag)

    def reset_pagination(self) -> None:
        self.page = 0

    def reset_selection(self) -> None:
        self.selected_recipe_ids = set()

    def toggle_recipe_selection(self, recipe_id: str) -> None:
        if recipe_id in self.selected_recipe_ids:
            self.selected_recipe_ids.discard(recipe_id)
        else:
            self.selected_recipe_ids.add(recipe_id)

    def to_dict(self) -> dict:
        return {
            "meal_type": self.meal_type,
            "category_id": self.category_id,
            "selected_filters": list(self.selected_filters),
            "page": self.page,
            "source": self.source,
            "current_recipe_id": self.current_recipe_id,
            "message_ids": self.message_ids,
            "selected_recipe_ids": list(self.selected_recipe_ids),
            "selection_context": self.selection_context,
            "page_recipe_ids": getattr(self, "page_recipe_ids", []) or [],
            "favourites_list_message_id": getattr(self, "favourites_list_message_id", None),
            "recipes_list_message_ids": getattr(self, "recipes_list_message_ids", []) or [],
        }

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> "UserContext":
        if data is None:
            return cls()
        return cls(
            meal_type=data.get("meal_type"),
            category_id=data.get("category_id"),
            selected_filters=set(data.get("selected_filters", [])),
            page=data.get("page", 0),
            source=data.get("source", "category"),
            current_recipe_id=data.get("current_recipe_id"),
            message_ids=data.get("message_ids", []),
            selected_recipe_ids=set(data.get("selected_recipe_ids", [])),
            selection_context=data.get("selection_context"),
            page_recipe_ids=data.get("page_recipe_ids") or [],
            favourites_list_message_id=data.get("favourites_list_message_id"),
            recipes_list_message_ids=data.get("recipes_list_message_ids") or [],
        )