import logging
import requests
from fastapi import FastAPI, HTTPException
from datamodel import *
import pika
import json
import uuid
import threading
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import uvicorn

# Настройка логирования
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

# Конфигурация
MAX_PLANES = 10
RABBITMQ_URL = "amqp://xnyyznus:OSOOLzaQHT5Ys6NPEMAU5DxTChNu2MUe@hawk.rmq.cloudamqp.com:5672/xnyyznus"
QUEUE_NAMES = {
    'food': 'tasks.catering',
    'baggage': '?'
}
INFO_PANEL_URL = "https://spicy-cloths-invent.loca.lt"

class Plane:
    def __init__(self, plane_id: str, flight_data: dict):
        logger.info(f"Creating new plane {plane_id}")
        self.plane_id = 'PL001'
        self.flight = flight_data
        self.planeParking = "P-1"
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
        try:
            self.connection = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
            self.channel = self.connection.channel()
            logger.info("Connected to RabbitMQ successfully")
        except Exception as e:
            logger.error(f"RabbitMQ connection failed: {str(e)}")
            raise

    def get_nearest_flight(self, plane_id: str):
        logger.info(f"Fetching flights for plane {plane_id}")
        try:

            response = requests.get(
                f"{INFO_PANEL_URL}/v1/flights",
                params={"type": "depart", "plane_id": plane_id}
            )
            flights = response.json()
            if not flights:
                logger.warning(f"No flights found for plane {plane_id}")
                return None
            
            nearest_flight = min(flights, key=lambda x: x["scheduledTime"])
            logger.debug(f"Found nearest flight: {nearest_flight}")
            return nearest_flight
                
        except Exception as e:
            logger.error(f"Error fetching flights: {str(e)}")
            return None

    def create_plane(self):
        try:
            if len(self.planes) >= MAX_PLANES:
                logger.warning("Maximum plane capacity reached")
                return

            plane_id = 'FL123'
            logger.info(f"Creating new plane {plane_id}")

            flight_data = self.get_nearest_flight(plane_id)
            if not flight_data:
                logger.error(f"No flight data available for {plane_id}")
                return

            plane = Plane(plane_id, flight_data)
            self.planes[str(plane_id)] = plane
            self.send_loading_tasks(plane_id, flight_data)
            logger.info(f"Successfully created plane {plane_id}")
            logger.info(plane.get_plane())

        except Exception as e:
            logger.error(f"Failed to create plane: {str(e)}")

    def send_loading_tasks(self, plane_id: UUID4, flight_data: dict):
        logger.info(f"Sending loading tasks for plane {plane_id}")
        tasks = {
            'fuel': {'amount': flight_data['requiredFuel']},
            #'passengers': {'passengers': flight_data['passengerList']},
            #'food': {'food': flight_data['foodOrder']},
            #'baggage': {'baggage': flight_data['baggageList']}
        }

        for task_type, payload in tasks.items():
            try:
                message = {
                    'plane_id': str(plane_id),
                    'payload': payload
                }
                self.channel.basic_publish(
                    exchange='',
                    routing_key=QUEUE_NAMES[task_type],
                    body=json.dumps(message),
                    properties=pika.BasicProperties(
                        delivery_mode=2
                    )
                )
                logger.debug(f"Sent {task_type} task to queue {QUEUE_NAMES[task_type]}")
            except Exception as e:
                logger.error(f"Failed to send {task_type} task: {str(e)}")

    def get_plane(self, plane_id: UUID4) -> Plane:
        logger.info(f"Fetching plane {plane_id}")
        plane = self.planes.get(str(plane_id))
        if not plane:
            logger.error(f"Plane {plane_id} not found")
            raise HTTPException(status_code=404, detail="Plane not found")
        return plane

board = Board()

def start_consumers():
    logger.info("Starting RabbitMQ consumers")
    try:
        connection = pika.BlockingConnection(
            pika.URLParameters(host=RABBITMQ_URL))
        channel = connection.channel()

        def callback(ch, method, properties, body):
            try:
                data = json.loads(body)
                plane_id = uuid.UUID(data['plane_id'])
                logger.info(f"Received message for plane {plane_id} from {method.routing_key}")

                plane = board.get_plane(plane_id)
                payload = data['payload']

                if method.routing_key == QUEUE_NAMES['fuel']:
                    logger.debug(f"Processing fuel loading for {plane_id}")
                    #handle_fuel_loading(plane, payload)
                elif method.routing_key == QUEUE_NAMES['passengers']:
                    logger.debug(f"Processing passengers loading for {plane_id}")
                    #handle_passengers_loading(plane, payload)
                elif method.routing_key == QUEUE_NAMES['food']:
                    logger.debug(f"Processing food loading for {plane_id}")
                    handle_food_loading(plane, payload)
                elif method.routing_key == QUEUE_NAMES['baggage']:
                    logger.debug(f"Processing baggage loading for {plane_id}")
                    handle_baggage_loading(plane, payload)

                logger.info(f"Successfully processed message for {plane_id}")

            except Exception as e:
                logger.error(f"Error processing message: {str(e)}")

        for queue in QUEUE_NAMES.values():
            channel.basic_consume(
                queue=queue,
                on_message_callback=callback,
                auto_ack=True
            )
            logger.debug(f"Subscribed to queue: {queue}")

        thread = threading.Thread(target=channel.start_consuming)
        thread.daemon = True
        thread.start()
        logger.info("RabbitMQ consumers started successfully")

    except Exception as e:
        logger.error(f"Failed to start consumers: {str(e)}")
'''
def handle_fuel_loading(plane: Plane, payload: dict):
    try:
        amount = payload.get('amount', 0)
        logger.info(f"Loading {amount} fuel for plane {plane.plane_id}")
        
        if amount < plane.minRequiredFuel:
            raise ValueError("Insufficient fuel")
        if amount > plane.maxFuel:
            raise ValueError("Fuel limit exceeded")
        
        plane.currentFuel = amount
        logger.info(f"Fuel loaded successfully for {plane.plane_id}")
        
    except Exception as e:
        logger.error(f"Fuel loading failed: {str(e)}")
        raise

def handle_passengers_loading(plane: Plane, payload: dict):
    try:
        passengers = payload.get('passengers', [])
        logger.info(f"Loading {len(passengers)} passengers for {plane.plane_id}")
        
        if len(passengers) > plane.maxCapacity:
            raise ValueError("Capacity exceeded")
        
        plane.passengers = passengers
        logger.info(f"Passengers loaded successfully for {plane.plane_id}")
        
    except Exception as e:
        logger.error(f"Passengers loading failed: {str(e)}")
        raise
'''
def handle_food_loading(plane: Plane, payload: dict):
    try:
        logger.info(f"Loading food for {plane.plane_id}")
        plane.food = payload.get('food', {})
        logger.info(f"Food loaded successfully: {plane.food}")
        
    except Exception as e:
        logger.error(f"Food loading failed: {str(e)}")
        raise

def handle_baggage_loading(plane: Plane, payload: dict):
    try:
        baggage = payload.get('baggage', [])
        logger.info(f"Loading {len(baggage)} baggage items for {plane.plane_id}")
        plane.baggage = baggage
        logger.info("Baggage loaded successfully")
        
    except Exception as e:
        logger.error(f"Baggage loading failed: {str(e)}")
        raise

@app.on_event("startup")
def startup():
    logger.info("Starting application initialization")
    try:
        scheduler.add_job(
            board.create_plane,
            trigger=IntervalTrigger(minutes=0.1),
            max_instances=1
        )
        scheduler.start()
        start_consumers()
        logger.info("Application started successfully")
    except Exception as e:
        logger.error(f"Application startup failed: {str(e)}")
        raise

@app.on_event("shutdown")
def shutdown():
    logger.info("Shutting down application")
    try:
        if board.connection and not board.connection.is_closed:
            board.connection.close()
            logger.info("RabbitMQ connection closed")
        scheduler.shutdown()
        logger.info("Scheduler stopped")
    except Exception as e:
        logger.error(f"Shutdown error: {str(e)}")

@app.post("/v1/board/initialize")
def initialize_flight(request: InitializeRequest):
    logger.info(f"Initializing flight for plane {request.plane_id}")
    try:
        flight_data = board.get_nearest_flight(request.plane_id)
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

@app.post("/v1/board/fuel")
def load_fuel(request: FuelRequest):
    logger.info(f"Manual fuel load request for {request.plane_id}")
    try:
        plane = board.get_plane(request.plane_id)
        #handle_fuel_loading(plane, {'amount': request.amount})
        logger.info("Manual fuel load successful")
        return {"currentFuel": plane.currentFuel}
    except Exception as e:
        logger.error(f"Manual fuel load failed: {str(e)}")
        raise

@app.get("/v1/board/{plane_id}", response_model=PlaneInfoResponse)
def get_plane_info(plane_id: UUID4):
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