# Metrology System Data Streaming

Listens to data transmitted by the Metrology System software (Motive) and forwards them to kafka.

## Usage



## Important Info

1. Rotation is provided in quaternions.
2. There exists a "_Tracking Valid_" parameter, for each individual rigid body, that is _True_ if the all markers of
the rigid body are in the field of view of the cameras. If a rigid body disappears from the field of view of the 
cameras, then the "_Tracking Valid_" parameter of the rigid body switches to _False_ and the rigid body's  last valid 
coordinates and rotation info are transmitted.
