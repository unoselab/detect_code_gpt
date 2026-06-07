def agc_mixed_001_01(self, model, *, skip_table_setup=False):
        """Create backing tables for a model and its non-abstract subclasses.

        :param model: Base model to bind.  Can be abstract.
        :param skip_table_setup: Don't create or verify the table in DynamoDB.  Default is False.
        :raises bloop.exceptions.InvalidModel: if ``model`` is not a subclass of :class:`~bloop.models.BaseModel`.
        """
        # Make sure we're looking at models
        if not issubclass(model, BaseModel):
            raise InvalidModel(f"{model} is not a subclass of BaseModel")

        if not skip_table_setup:
            self.create_table(model)

        self.bind_model(model)

        for subclass in model.__subclasses__():
            if not subclass._abstract:
                self.bind(subclass, skip_table_setup=skip_table_setup) 

def hwc_mixed_001_02(content, indent=None):
    """
    Serializes a python object as JSON

    This method uses the DJangoJSONEncoder to to ensure that python objects
    such as Decimal objects are properly serialized. It can also serialize
    Django QuerySet objects.
    """
    if isinstance(content, QuerySet):
        json_serializer = serializers.get_serializer('json')()
        serialized_content = json_serializer.serialize(content, ensure_ascii=False, indent=indent)
    else:
        try:
            serialized_content = json.dumps(content, cls=DecimalEncoder, ensure_ascii=False, indent=indent)
        except TypeError:
            # Fix for Django 1.5
            serialized_content = json.dumps(content, ensure_ascii=False, indent=indent)
    return serialized_content 

def agc_mixed_001_03(self):
        """Helper:  adjust orders based on cursors, where clauses."""
        if self.cursor:
            self.orders = [
                (self.cursor, self.cursor_direction)
            ] + self.orders
        if self.where:
            self.orders = [
                (self.where, self.where_direction)
            ] + self.orders 

def agc_mixed_001_04(instance, encoding='utf-8'):
    """Convert an instance recursively to string."""
    if isinstance(instance, dict):
        return {k: to_str(v, encoding) for k, v in instance.items()}
    elif isinstance(instance, list):
        return [to_str(v, encoding) for v in instance]
    elif isinstance(instance, tuple):
        return tuple(to_str(v, encoding) for v in instance)
    elif isinstance(instance, str):
        return instance
    elif isinstance(instance, bytes):
        return instance.decode(encoding)
    else:
        return str(instance) 

def hwc_mixed_001_05(self):
    """Creates a socket, connects it to the nailgun and returns the connected socket.

    :returns: a connected `socket.socket`.
    :raises: `NailgunClient.NailgunConnectionError` on failure to connect.
    """
    sock = RecvBufferedSocket(socket.socket(socket.AF_INET, socket.SOCK_STREAM))
    try:
      sock.connect(self._address)
    except (socket.error, socket.gaierror) as e:
      logger.debug('Encountered socket exception {!r} when attempting connect to nailgun'.format(e))
      sock.close()
      raise self.NailgunConnectionError(
        address=self._address_string,
        pid=self._maybe_last_pid(),
        pgrp=self._maybe_last_pgrp(),
        wrapped_exc=e,
      )
    else:
      return sock 

def hwc_mixed_001_06(self, name):
        u"""
        Возвращает обработчик конвертации с указанным именем

        :param name: Имя обработчика
        :return: callable
        """
        try:
            handler = self.conversion_table[name]
        except KeyError:
            raise KeyError((
                u'Конвертирующий тип с именем {} отсутствует '
                u'в таблице соответствия!'
            ).format(name))

        return handler
