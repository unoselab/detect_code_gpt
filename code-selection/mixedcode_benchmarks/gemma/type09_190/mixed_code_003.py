def hwc_mixed_003_01(val, shape, default=None, dtype=np.float64):
    """Ensure an object is an array with the specified shape."""
    assert val is not None or default is not None
    if hasattr(val, '__len__') and len(val) == 0:  # pragma: no cover
        val = None
    # Do nothing if the array is already correct.
    if (isinstance(val, np.ndarray) and
            val.shape == shape and
            val.dtype == dtype):
        return val
    out = np.zeros(shape, dtype=dtype)
    # This solves `ValueError: could not broadcast input array from shape (n)
    # into shape (n, 1)`.
    if val is not None and isinstance(val, np.ndarray):
        if val.size == out.size:
            val = val.reshape(out.shape)
    out.flat[:] = val if val is not None else default
    assert out.shape == shape
    return out 

def agc_mixed_003_02(self, intervention, id=None):
        """
        Add an intervention to intervention/human section.
        intervention is either ElementTree or xml snippet
        """
        import xml.etree.ElementTree as ET
        if isinstance(intervention, str):
            intervention = ET.fromstring(intervention)

        section = self.find('.//intervention/human')
        if section is None:
            intervention_root = self.find('.//intervention')
            if intervention_root is not None:
                section = ET.SubElement(intervention_root, 'human')
            else:
                intervention_root = ET.SubElement(self.root, 'intervention')
                section = ET.SubElement(intervention_root, 'human')

        if id is not None:
            intervention.set('id', str(id))

        section.append(intervention) 

def agc_mixed_003_03(x, y, final_length_divisible_by=1, axis=1):
  """Pad tensors x and y on axis 1 so that they have the same length."""
  import torch.nn.functional as F
  import torch

  max_len = max(x.shape[axis], y.shape[axis])
  if final_length_divisible_by > 1:
      max_len = ((max_len + final_length_divisible_by - 1) // final_length_divisible_by) * final_length_divisible_by

  def get_padding(tensor):
      current_len = tensor.shape[axis]
      pad_total = max_len - current_len
      # F.pad expects padding from last dimension backwards
      # We need to construct a padding list for all dimensions
      padding = [0] * (2 * tensor.ndim)
      # Index for the specific axis from the end
      axis_idx_from_end = tensor.ndim - 1 - axis
      # F.pad uses (left, right, top, bottom, ...)
      # For the target axis, we pad only on the right (end)
      padding[2 * axis_idx_from_end + 1] = pad_total
      return padding

  x_padded = F.pad(x, get_padding(x))
  y_padded = F.pad(y, get_padding(y))
  return x_padded, y_padded 

def hwc_mixed_003_04(self, request_type, uri, payload):
        """Build and send a command."""
        self.command_count += 1

        if payload is None:
            payload = {}

        message = {
            'id': "{}_{}".format(type, self.command_count),
            'type': request_type,
            'uri': "ssap://{}".format(uri),
            'payload': payload,
        }

        self.last_response = None

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(asyncio.wait_for(self._command(message), self.timeout_connect, loop=loop))
        finally:
            loop.close() 

def agc_mixed_003_05(self):
        """
        Generates _field_map, _field_ids and _oid_nums for use in parsing
        """

        self._field_map = {}
        self._field_ids = {}
        self._oid_nums = {}

        # This is a generic implementation of a setup method for field mapping.
        # Since the specific data source isn't provided, it initializes the maps.
        # In a real scenario, this would iterate over a schema or definition.
        if hasattr(self, 'fields'):
            for idx, field in enumerate(self.fields):
                name = field.name
                self._field_map[name] = idx
                self._field_ids[name] = field.id
                self._oid_nums[field.id] = idx 

def hwc_mixed_003_06(logger, level='info'):
    """
    增加console作为日志输入.
    """
    logger.setLevel(getattr(logging, level.upper()))

    if not logger.handlers:
        # Set up color if we are in a tty and curses is installed
        color = False
        if curses and sys.stderr.isatty():
            try:
                curses.setupterm()
                if curses.tigetnum("colors") > 0:
                    color = True
            except:
                pass
        console = logging.StreamHandler()
        console.setFormatter(_LogFormatter(color=color))
        logger.addHandler(console)
    return logger
