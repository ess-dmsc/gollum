# Metrology System Data Streaming

Listens to data transmitted by the Metrology System software (Motive) and forwards them to Ksafka.

## Usage

```
python main.py --multicast_address 127.0.0.1 --local_address 127.0.0.1 --kafka_broker 10.100.1.19:9092 --topic ymir_gollum
```
Also possible to supply Kafka security settings:
- --security-protocol
- --sasl-mechanism
- --sasl-username
- --sasl-password
- --ssl-cafile

## Important Info

1. Rotation is currently provided in degrees.
2. There exists a "_Tracking Valid_" parameter, for each individual rigid body, that is _True_ if the all markers of
the rigid body are in the field of view of the cameras. If a rigid body disappears from the field of view of the 
cameras, then the "_Tracking Valid_" parameter of the rigid body switches to _False_ and the rigid body's  last valid 
coordinates and rotation info are transmitted.
