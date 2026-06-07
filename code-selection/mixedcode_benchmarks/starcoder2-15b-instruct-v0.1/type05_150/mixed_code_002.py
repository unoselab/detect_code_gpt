def hwc_mixed_002_01(self):
        """
        Return an iterator over all expression levels
        """
        for dataset in self.getDatasets():
            for rnaQuantificationSet in dataset.getRnaQuantificationSets():
                for rnaQuantification in \
                        rnaQuantificationSet.getRnaQuantifications():
                    for expressionLevel in \
                            rnaQuantification.getExpressionLevels():
                        yield expressionLevel 

def agc_mixed_002_02(
            self, M_c, X_L_list, X_D_list, Y, Q):
        """Calculate probability of a cell taking a value given a latent state.

        :param Y: A list of constraints to apply when querying.  Each constraint
            is a triplet of (r,d,v): r is the row index, d is the column
            index and v is the value of the constraint
        :type Y: list of lists

        :param Q: A list of values to query.  Each value is triplet of (r,d,v):
            r is the row index, d is the column index, and v is the value at
            which the density is evaluated.
        :type Q: list of lists

        :returns: list of floats -- probabilities of the values specified by Q
        """
        probabilities = []
        for r, d, v in Q:
            probability = 0.0
            for x_l in X_L_list:
                for x_d in X_D_list:
                    probability += self.predictive_probability_multistate(
                        M_c, x_l, x_d, Y, r, d, v)
            probabilities.append(probability)
        return probabilities 

def hwc_mixed_002_03(train_start=0, train_end=50000, test_start=0, test_end=10000):
  """
  Preprocess CIFAR10 dataset
  :return:
  """


  # These values are specific to CIFAR10
  img_rows = 32
  img_cols = 32
  nb_classes = 10

  # the data, shuffled and split between train and test sets
  (x_train, y_train), (x_test, y_test) = cifar10.load_data()

  if tf.keras.backend.image_data_format() == 'channels_first':
    x_train = x_train.reshape(x_train.shape[0], 3, img_rows, img_cols)
    x_test = x_test.reshape(x_test.shape[0], 3, img_rows, img_cols)
  else:
    x_train = x_train.reshape(x_train.shape[0], img_rows, img_cols, 3)
    x_test = x_test.reshape(x_test.shape[0], img_rows, img_cols, 3)
  x_train = x_train.astype('float32')
  x_test = x_test.astype('float32')
  x_train /= 255
  x_test /= 255
  print('x_train shape:', x_train.shape)
  print(x_train.shape[0], 'train samples')
  print(x_test.shape[0], 'test samples')

  # convert class vectors to binary class matrices
  y_train = np_utils.to_categorical(y_train, nb_classes)
  y_test = np_utils.to_categorical(y_test, nb_classes)

  x_train = x_train[train_start:train_end, :, :, :]
  y_train = y_train[train_start:train_end, :]
  x_test = x_test[test_start:test_end, :]
  y_test = y_test[test_start:test_end, :]

  return x_train, y_train, x_test, y_test 

def agc_mixed_002_04(file_patterns, top=HERE):
    """Expand file patterns to a list of paths.

    Parameters
    -----------
    file_patterns: list or str
        A list of glob patterns for the data file locations.
        The globs can be recursive if they include a `**`.
        They should be relative paths from the top directory or
        absolute paths.
    top: str
        the directory to consider for data files

    Note:
    Files in `node_modules` are ignored.
    """
    if not isinstance(file_patterns, list):
        file_patterns = [file_patterns]
    file_paths = []
    for pattern in file_patterns:
        if os.path.isabs(pattern):
            top = os.path.dirname(pattern)
            pattern = os.path.basename(pattern)
        if '**' in pattern:
            file_paths.extend(glob.glob(os.path.join(top, '**', pattern.split('**')[-1]), recursive=True))
        else:
            file_paths.extend(glob.glob(os.path.join(top, pattern)))
    file_paths = [path for path in file_paths if not os.path.basename(path).startswith('.')]
    file_paths = [path for path in file_paths if not os.path.basename(path).startswith('node_modules')]

    return file_paths 

def hwc_mixed_002_05(uri, nonce, signature, auth_token=''):
    """
    Validates requests made by Plivo to your servers.

    :param uri: Your server URL
    :param nonce: X-Plivo-Signature-V2-Nonce
    :param signature: X-Plivo-Signature-V2 header
    :param auth_token: Plivo Auth token
    :return: True if the request matches signature, False otherwise
    """

    auth_token = bytes(auth_token.encode('utf-8'))
    nonce = bytes(nonce.encode('utf-8'))
    signature = bytes(signature.encode('utf-8'))

    parsed_uri = urlparse(uri.encode('utf-8'))
    base_url = urlunparse((parsed_uri.scheme.decode('utf-8'),
                           parsed_uri.netloc.decode('utf-8'),
                           parsed_uri.path.decode('utf-8'), '', '',
                           '')).encode('utf-8')

    return encodestring(hnew(auth_token, base_url + nonce, sha256)
                        .digest()).strip() == signature 

def agc_mixed_002_06(self, game_image):
        """Return a board object matching the board in the game image.
        Return None if any tiles are not identified.
        """
        # board image
        board = Board()
        for row in range(self.board_height):
            for col in range(self.board_width):
                tile_image = game_image.get_tile_image(row, col)
                tile_type = self.tile_classifier.classify_tile(tile_image)
                if tile_type is None:
                    return None
                board.set_tile(row, col, tile_type)
        return board
