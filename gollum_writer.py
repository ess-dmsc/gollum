from confluent_kafka import Producer


producer_config = {
        "bootstrap.servers": "127.0.0.1",
        "message.max.bytes": "20000000",
    }
producer = Producer(producer_config)

producer.produce("gollum", "test message 1".encode())
producer.flush()
