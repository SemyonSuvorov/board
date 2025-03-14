import logging
import random
import requests
from fastapi import FastAPI, HTTPException
from datamodel import *

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import uvicorn


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = FastAPI()
scheduler = BackgroundScheduler()


MAX_PLANES = 10


INFO_PANEL_URL = "https://curly-mammals-give.loca.lt"
HANDLING_SUPERVIZOR_URL = "https://chatty-cities-film.loca.lt"

class Plane:
    def __init__(self, plane_id: str, flight_data: dict):
        logger.info(f"Creating new plane {plane_id}")
        self.plane_id = plane_id
        self.flight = flight_data
        self.planeParking = flight_data['planeParking']
        self.currentFuel = 0
        self.minRequiredFuel = flight_data.get('minFuelForFlight', 3000)
        self.maxFuel = flight_data.get('maxFuel', 5000)
        self.maxCapacity = flight_data.get('maxCapacity', 300)
        #self.passengers = []
        self.food = {}
        self.baggage = []
        self.status = "created"
        logger.debug(f"Plane created: {self.__dict__}")
    def get_plane(self):
        return {"plane_id": self.plane_id, "flight": self.flight
                , "planeParking": self.planeParking, "currentFuel":self.currentFuel
                , "minRequiredFuel": self.minRequiredFuel, "maxFuel":self.maxFuel
                , "maxCapacity": self.maxCapacity, "food": self.food, "baggage": self.baggage, "status": self.status}

class Board:
    def __init__(self):
        logger.info("Initializing Board service")
        self.planes: Dict[str, Plane] = {}

    def get_nearest_depart(self, plane_id: str):
        logger.info(f"Fetching flights for plane {plane_id}")
        try:
            response = requests.get(
                f"{INFO_PANEL_URL}/v1/flights",
            )

            logger.info(response)

            flights = response.json()
            
            departs = [flight for flight in flights if flight['type'] == 'depart']
            departs = [flight for flight in flights if flight['planeId'] == plane_id]
            if not departs:
                logger.warning(f"No depart flights found for plane {plane_id}")
                return None
            nearest_depart_flight = min(departs, key=lambda x: x["scheduledTime"])
            logger.debug(f"Found nearest flight: {nearest_depart_flight}")
            return nearest_depart_flight
                
        except Exception as e:
            logger.error(f"Error fetching flights: {str(e)}")
            return None
        
    def get_nearest_arrive(self, plane_id: str):
        logger.info(f"Fetching flights for plane {plane_id}")
        try:
            response = requests.get(
                f"{INFO_PANEL_URL}/v1/flights",
            )

            logger.info(response)

            flights = response.json()
            
            arrives = [flight for flight in flights if flight['type'] == 'arrive']
            arrives = [flight for flight in flights if flight['status'] == 'SoonArrived']
            arrives = [flight for flight in flights if flight['planeId'] == plane_id]
            if not arrives:
                logger.warning(f"No arrive flights found for plane {plane_id}")
                return None
            nearest_arrive_flight = min(arrives, key=lambda x: x["scheduledTime"])
            logger.debug(f"Found nearest arrive flight: {nearest_arrive_flight}")
            return nearest_arrive_flight
                
        except Exception as e:
            logger.error(f"Error fetching flights: {str(e)}")
            return None

    def create_plane(self):
        try:
            if len(self.planes) >= MAX_PLANES:
                logger.warning("Maximum plane capacity reached")
                return

            plane_ids = ['PL-1', 'PL777', 'PL002']
            available_plane_ids = [pid for pid in plane_ids if pid not in self.planes]

            # Перебираем доступные plane_id, пока не найдем подходящий
            while available_plane_ids:
                current_plane = random.choice(available_plane_ids)
                available_plane_ids.remove(current_plane)  # Убираем проверенный ID из списка
                
                logger.info(f"Trying to create plane {current_plane}")
                flight_data_depart = self.get_nearest_depart(current_plane)
                flight_data_arrive = self.get_nearest_arrive(current_plane)
                
                if not flight_data_depart:
                    logger.warning(f"No flight depart for {current_plane}, trying next...")
                    if flight_data_arrive:
                        logger.info(f"Flight arrive for {current_plane}")
                        flight_id = flight_data_arrive.get("flightId")
                        if any(p.flight_id == flight_id for p in self.planes.values()):
                            logger.warning(f"Flight {flight_id} is busy, skipping {current_plane}")
                            continue

                        plane = Plane(current_plane, flight_data_depart)
                        self.planes[current_plane] = plane
                        logger.info(f"Successfully created plane arrive {current_plane}")
                        logger.info(plane.get_plane())
                        return  
                    continue
                else:  
                    flight_id = flight_data_depart.get("flightId")
                    if any(p.flight_id == flight_id for p in self.planes.values()):
                        logger.warning(f"Flight {flight_id} is busy, skipping {current_plane}")
                        continue

                    # Если все проверки пройдены - создаем самолет
                    plane = Plane(current_plane, flight_data_depart)
                    self.planes[current_plane] = plane
                    self.send_loading_fuel(current_plane, flight_data_depart)
                    logger.info(f"Successfully created plane depart {current_plane}")
                    logger.info(plane.get_plane())
                    return  # Выходим после успешного создания

            logger.error("No available planes with valid flights")
            
        except Exception as e:
            logger.error(f"Failed to create plane: {str(e)}")


    def send_loading_fuel(self, plane_id: str, flight_data: dict):
        logger.info(f"Sending loading fuel for plane to handling supervizor {plane_id}")
        data = {'planeId': plane_id, 'planeParking': flight_data['planeParking'],'fuelAmount': flight_data['requiredFuel']}
        try:
            requests.post(f"{HANDLING_SUPERVIZOR_URL}/v1/tasks/refuel",
                    json=data)
            logger.debug(f"Sent refuel task to queue handling supervizor")
        except Exception as e:
            logger.error(f"Failed to send refuel task: {str(e)}")

    def get_plane(self, plane_id: str) -> Plane:
        logger.info(f"Fetching plane {plane_id}")
        plane = self.planes.get(str(plane_id))
        if not plane:
            logger.error(f"Plane {plane_id} not found")
            raise HTTPException(status_code=404, detail="Plane not found")
        return plane

board = Board()


@app.on_event("startup")
def startup():
    scheduler.add_job(
        board.create_plane,
        trigger=IntervalTrigger(minutes=0.1),
        max_instances=1
    )
    scheduler.start()

@app.on_event("shutdown")
def shutdown():
    logger.info("Shutting down application")
    try:
        scheduler.shutdown()
        logger.info("Scheduler stopped")
    except Exception as e:
        logger.error(f"Shutdown error: {str(e)}")

@app.post("/v1/board/initialize")
def initialize_flight(request: InitializeRequest):
    logger.info(f"Initializing flight for plane {request.plane_id}")
    try:
        flight_data = board.get_nearest_depart(request.plane_id)
        if not flight_data:
            logger.error("No available flights found")
            raise HTTPException(status_code=404, detail="Рейсы не найдены")

        if str(request.plane_id) not in board.planes:
            board.planes[str(request.plane_id)] = Plane(request.plane_id, flight_data)
            logger.info(f"Plane {request.plane_id} initialized successfully")

        return {
            "flight_id": flight_data['flight_id'],
            "scheduledTime": flight_data['scheduledTime'],
            "details": flight_data['details']
        }
    except Exception as e:
        logger.error(f"Initialization failed: {str(e)}")
        raise


@app.get("/v1/board/{plane_id}", response_model=PlaneInfoResponse)
def get_plane_info(plane_id: str):
    logger.info(f"Info request for plane {plane_id}")
    try:
        plane = board.get_plane(plane_id)
        logger.debug(f"Returning plane info: {plane.__dict__}")
        return {
            "plane_id": plane.plane_id,
            "flight": plane.flight,
            "planeParking": plane.planeParking,
            "baggage": plane.baggage,
            "currentFuel": plane.currentFuel,
            "minRequiredFuel": plane.minRequiredFuel,
            "maxFuel": plane.maxFuel,
            "maxCapacity": plane.maxCapacity,
            "food": plane.food,
            "passengers": plane.passengers,
            "numPassengers": len(plane.passengers)
        }
    except Exception as e:
        logger.error(f"Info request failed: {str(e)}")
        raise


logger.info("Starting application server")
uvicorn.run(app, host="0.0.0.0", port=8005)