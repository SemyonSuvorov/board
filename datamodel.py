from pydantic import BaseModel
from typing import Dict, List, Optional


class InitializeRequest(BaseModel):
  plane_id: str


class FuelRequest(BaseModel):
  plane_id: str
  amount: int


class PassengersRequest(BaseModel):
  plane_id: str
  passengers: List[str]


class FoodRequest(BaseModel):
  plane_id: str
  food: Dict[str, int]


class BaggageRequest(BaseModel):
  plane_id: str
  baggage: List[str]


class TakeoffRequest(BaseModel):
  plane_id: str


class PlaneInfoResponse(BaseModel):
  plane_id: str
  flight: Optional[dict]
  planeParking: Optional[str]
  baggage: List[str]
  currentFuel: int
  minRequiredFuel: int
  maxFuel: int
  maxCapacity: int
  food: Dict[str, int]
  passengers: List[str]
  numPassengers: int


  def get_plane(self):
        return {"plane_id": self.plane_id, "flight": self.flight
                , "planeParking": self.planeParking, "currentFuel":self.currentFuel
                , "minRequiredFuel": self.minRequiredFuel, "maxFuel":self.maxFuel
                , "maxCapacity": self.maxCapacity, "food": self.food, "baggage": self.baggage, "status": self.status}