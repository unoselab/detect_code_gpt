def agc_mixed_003_01(self, key: str, value: str):
        """
        Add a new metadata to the message

        Args:
          key (str): name of the metadata
          value (str): value of the metadata

        """
        if not isinstance(key, str):
            raise TypeError(f"Metadata key must be a string, got {type(key).__name__}")
        if not isinstance(value, str):
            raise TypeError(f"Metadata value must be a string, got {type(value).__name__}")

        # Ensure the instance has a metadata container
        if not hasattr(self, "metadata") or self.metadata is None:
            self.metadata = {}

        # Store the metadata
        self.metadata[key] = value 

def hwc_mixed_003_02(signal, receiver):
    """Disconnect the receiver `func` from the signal, identified by
    `signal_id`.

    Args:
        signal: The signal identifier.
        receiver: The callable receiver to disconnect.

    Returns:
        True if the receiver was successfully disconnected. False otherwise.
    """
    inputkey = __make_id(receiver)

    with __lock:
        __purge()
        receivers = __receivers.get(signal)

        for idx in six.moves.range(len(receivers)):
            connected = receivers[idx]()

            if inputkey != __make_id(connected):
                continue

            del receivers[idx]
            return True  # receiver successfully disconnected!

    return False 

def hwc_mixed_003_03(self, byts):
        """
        Decode an envelope dict and decrypt the given bytes.

        Args:
            byts (bytes): Bytes to decrypt.

        Returns:
            bytes: Decrypted message.
        """
        envl = s_msgpack.un(byts)
        iv = envl.get('iv', b'')
        asscd = envl.get('asscd', b'')
        data = envl.get('data', b'')

        decryptor = AESGCM(self.ekey)

        try:
            data = decryptor.decrypt(iv, data, asscd)
        except Exception:
            logger.exception('Error decrypting data')
            return None
        return data 

def agc_mixed_003_04(value):
    """For numbers 1-9, returns the number spelled out. Otherwise, returns the
    number. This follows Associated Press style.  This always returns a string
    unless the value was not int-able, unlike the Django filter."""
    try:
        i = int(value)
    except (TypeError, ValueError):
        return value
    words = {
        1: "one",
        2: "two",
        3: "three",
        4: "four",
        5: "five",
        6: "six",
        7: "seven",
        8: "eight",
        9: "nine",
    }
    return words.get(i, str(i)) 

def agc_mixed_003_05(picklefile, model, vocab, doc_labels, dtm=None, **kwargs):
    """Save a LDA model as pickle file."""
    import os
    import pickle

    # Prepare data to be pickled
    payload = {"model": model, "vocab": vocab, "doc_labels": doc_labels}
    if dtm is not None:
        payload["dtm"] = dtm
    if kwargs:
        payload.update(kwargs)

    # Ensure target directory exists
    dir_name = os.path.dirname(picklefile)
    if dir_name and not os.path.isdir(dir_name):
        os.makedirs(dir_name, exist_ok=True)

    # Write the payload to the specified pickle file
    with open(picklefile, "wb") as f:
        pickle.dump(payload, f, protocol=pickle.HIGHEST_PROTOCOL) 

def hwc_mixed_003_06(self, input_entity, coefficients, duplicate=True):
        """Transforms all elementary entities symmetrically to a plane. The vector
        should contain four expressions giving the coefficients of the plane's equation.
        """
        d = {1: "Line", 2: "Surface", 3: "Volume"}
        entity = "{}{{{}}};".format(d[input_entity.dimension], input_entity.id)

        if duplicate:
            entity = "Duplicata{{{}}}".format(entity)

        self._GMSH_CODE.append(
            "Symmetry {{{}}} {{{}}}".format(
                ", ".join([str(co) for co in coefficients]), entity
            )
        )
        return
