# Convert command-line args to Kafka library options.

def get_kafka_security_config(
    protocol=None,
    mechanism=None,
    username=None,
    password=None,
    cafile=None,
):
    """
    Create security configuration for kafka-python from just-bin-it options.
    If no protocol is passed, PLAINTEXT is returned in the configuration.

    :param protocol: Protocol used to communicate with brokers.
    :param mechanism: SASL mechanism.
    :param username: SASL username.
    :param password: SASL password.
    :param cafile: Path to SSL CA file.
    :return: Configuration dict.
    """
    supported_security_protocols = ["PLAINTEXT", "SASL_PLAINTEXT", "SASL_SSL"]
    supported_sasl_mechanisms = ["PLAIN", "SCRAM-SHA-512", "SCRAM-SHA-256"]

    config = {}

    if protocol is None:
        protocol = "PLAINTEXT"
    elif protocol not in supported_security_protocols:
        raise Exception(
            f"Kafka security protocol {protocol} not supported, use {supported_security_protocols}"
        )

    config["security.protocol"] = protocol

    if "SASL_" in protocol:
        if mechanism not in supported_sasl_mechanisms:
            raise Exception(
                f"SASL mechanism {mechanism} not supported, use {supported_sasl_mechanisms}"
            )

        config["sasl.mechanism"] = mechanism

        if not username or not password:
            raise Exception(f"Username and password are required with {protocol}")

        config["sasl.username"] = username
        config["sasl.password"] = password

    if "_SSL" in protocol:
        config["ssl.ca.location"] = cafile

    return config
