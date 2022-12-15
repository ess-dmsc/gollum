# Metrology System Data Streaming

Listens to data transmitted by the Metrology System software (Motive) and forwards them to kafka.

## Usage

Run main.py, including the following arguments:

Argument 1 is the _Motive_ client address ("-mc", "--motive_client"): 127.0.0.1
Argument 2 is the _Motive_ server address ("-ms", "--motive_server"): 127.0.0.1 
Argument 3 is the _Kafka_ server address ("-ks", "--kafka_server"): [::1]:9092

## Important Info

1. Rotation is provided in quaternions.
2. There exists a "_Tracking Valid_" parameter, for each individual rigid body, that is _True_ if the all markers of
the rigid body are in the field of view of the cameras. If a rigid body disappears from the field of view of the 
cameras, then the "_Tracking Valid_" parameter of the rigid body switches to _False_ and the rigid body's  last valid 
coordinates and rotation info are transmitted.
