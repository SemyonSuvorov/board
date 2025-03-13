from pydantic import BaseModel, UUID4
from typing import Dict, List, Optional


class InitializeRequest(BaseModel):
  plane_id: UUID4


class FuelRequest(BaseModel):
  plane_id: UUID4
  amount: int


class PassengersRequest(BaseModel):
  plane_id: UUID4
  passengers: List[UUID4]


class FoodRequest(BaseModel):
  plane_id: UUID4
  food: Dict[str, int]


class BaggageRequest(BaseModel):
  plane_id: UUID4
  baggage: List[UUID4]


class TakeoffRequest(BaseModel):
  plane_id: UUID4


class PlaneInfoResponse(BaseModel):
  plane_id: UUID4
  flight: Optional[dict]
  planeParking: Optional[str]
  baggage: List[UUID4]
  currentFuel: int
  minRequiredFuel: int
  maxFuel: int
  maxCapacity: int
  food: Dict[str, int]
  passengers: List[UUID4]
  numPassengers: int


  def get_plane(self):
        return {"plane_id": self.plane_id, "flight": self.flight
                , "planeParking": self.planeParking, "currentFuel":self.currentFuel
                , "minRequiredFuel": self.minRequiredFuel, "maxFuel":self.maxFuel
                , "maxCapacity": self.maxCapacity, "food": self.food, "baggage": self.baggage, "status": self.status}