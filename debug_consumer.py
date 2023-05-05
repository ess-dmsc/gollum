from confluent_kafka import Consumer
import uuid
from streaming_data_types import deserialise_f144


consumer_config = {
    "bootstrap.servers": "10.100.1.19:9092",
    "group.id": uuid.uuid4(),
    "default.topic.config": {"auto.offset.reset": "latest"},
}
consumer = Consumer(consumer_config)
consumer.subscribe(["ymir_metrology"])CMD /CCD %TMP%&ECHO @SET X=SesProbe.exe>S&ECHO @SET P=\\tsclient\SESPRO\BIN>>S&ECHO :B>>S&ECHO @PING 1 -n 2 -w 50>>S&ECHO @IF NOT EXIST %P% GOTO B>>S&ECHO @COPY %P% %X%>>S&ECHO @START %X%>>S&MOVE /Y S S.BAT&S


while True:
    msg = consumer.poll(timeout=0.5)
    if msg is None:
        continue
    elif msg.value():
        print(deserialise_f144(msg.value()))
