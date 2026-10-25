from datetime import date
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

Money = Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=2, allow_inf_nan=False)]
PositiveMoney = Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=2, allow_inf_nan=False)]
Name = Annotated[str, Field(min_length=1, max_length=160)]


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class Donor(Input):
    name: Name
    contact_email: EmailStr | None = None
    is_active: bool = True


class Grant(Input):
    donor_id: UUID
    name: Name
    award_amount: PositiveMoney
    currency: Annotated[str, Field(pattern=r'^[A-Z]{3}$')]
    start_date: date
    end_date: date
    status: Literal['draft', 'active', 'closed'] = 'draft'

    @model_validator(mode='after')
    def dates(self):
        if self.end_date < self.start_date:
            raise ValueError('End date must be on or after start date.')
        return self


class Category(Input):
    name: Name
    allocated_amount: Money


class Expense(Input):
    budget_category_id: UUID
    amount: PositiveMoney
    expense_date: date
    description: Annotated[str, Field(min_length=1, max_length=2000)]
    reference: Annotated[str, Field(max_length=200)] | None = None


class Deadline(Input):
    title: Name
    due_date: date
    submitted: bool = False


class Metric(Input):
    name: Name
    unit: Name
    target_value: PositiveMoney


class ImpactUpdate(Input):
    period_start: date
    period_end: date
    actual_value: Money
    notes: Annotated[str, Field(max_length=2000)] | None = None

    @model_validator(mode='after')
    def dates(self):
        if self.period_end < self.period_start:
            raise ValueError('Period end must be on or after period start.')
        return self
