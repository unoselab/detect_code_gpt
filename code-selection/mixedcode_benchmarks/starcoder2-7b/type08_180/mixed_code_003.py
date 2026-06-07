def agc_mixed_003_01(self, stream):
        """Parses the keys + values from a config file."""

        for line in stream:
            line = line.strip()
            if line and not line.startswith('#'):
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                if key in self.keys:
                    self.keys[key].append(value)
                else:
                    self.keys[key] = [value] 

def hwc_mixed_003_02(args):
    """Validate provided arguments and act on --help."""
    # Check correctness of similarity dataset names
    for dataset_name in args.similarity_datasets:
        if dataset_name.lower() not in map(
                str.lower,
                nlp.data.word_embedding_evaluation.word_similarity_datasets):
            print('{} is not a supported dataset.'.format(dataset_name))
            sys.exit(1)

    # Check correctness of analogy dataset names
    for dataset_name in args.analogy_datasets:
        if dataset_name.lower() not in map(
                str.lower,
                nlp.data.word_embedding_evaluation.word_analogy_datasets):
            print('{} is not a supported dataset.'.format(dataset_name))
            sys.exit(1) 

def hwc_mixed_003_03(self):
        """Visualizes water bridges"""
        grp = self.getPseudoBondGroup("Water Bridges-%i" % self.tid, associateWith=[self.model])
        grp.lineWidth = 3
        for i, wbridge in enumerate(self.plcomplex.waterbridges):
            c = grp.newPseudoBond(self.atoms[wbridge.water_id], self.atoms[wbridge.acc_id])
            c.color = self.colorbyname('cornflower blue')
            self.water_ids.append(wbridge.water_id)
            b = grp.newPseudoBond(self.atoms[wbridge.don_id], self.atoms[wbridge.water_id])
            b.color = self.colorbyname('cornflower blue')
            self.water_ids.append(wbridge.water_id)
            if wbridge.protisdon:
                self.bs_res_ids.append(wbridge.don_id)
            else:
                self.bs_res_ids.append(wbridge.acc_id) 

def agc_mixed_003_04(self, data):
        """ this functions extracts the code, reason from the close body
        if they exists, and if the self.on_close except three arguments """
        # if the on_close callback is "old", just return empty list
        code = None
        reason = None
        if data:
            try:
                data = json.loads(data)
                if 'code' in data:
                    code = data['code']
                if'reason' in data:
                    reason = data['reason']
            except:
                pass
        return code, reason 

def hwc_mixed_003_05(namespace='default', **kwargs):
    """
    Return a list of kubernetes configmaps defined in the namespace

    CLI Examples::

        salt '*' kubernetes.configmaps
        salt '*' kubernetes.configmaps namespace=default
    """
    cfg = _setup_conn(**kwargs)
    try:
        api_instance = kubernetes.client.CoreV1Api()
        api_response = api_instance.list_namespaced_config_map(namespace)

        return [secret['metadata']['name'] for secret in api_response.to_dict().get('items')]
    except (ApiException, HTTPError) as exc:
        if isinstance(exc, ApiException) and exc.status == 404:
            return None
        else:
            log.exception(
                'Exception when calling '
                'CoreV1Api->list_namespaced_config_map'
            )
            raise CommandExecutionError(exc)
    finally:
        _cleanup(**cfg) 

def agc_mixed_003_06(args):
  """
  build and return a UI object for this script.

  :param args: raw arguments to parse
  """
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument(
    '-i', '--input',
    help='input file',
    required=True,
    type=str
  )
  parser.add_argument(
    '-o', '--output',
    help='output file',
    required=True,
    type=str
  )
  parser.add_argument(
    '-s', '--sample',
    help='sample name',
    required=True,
    type=str
  )
  parser.add_argument(
    '-t', '--target',
    help='target name',
    required=True,
    type=str
  )
  parser.add_argument(
    '-c', '--config',
    help='config file',
    required=True,
    type=str
  )
  parser.add_argument(
    '-v', '--verbose',
    help='verbose output',
    action='store_true'
  )
  parser.add_argument(
    '-d', '--debug',
    help='debug output',
    action='store_true'
  )
  parser.add_argument(
    '-q', '--quiet',
    help='quiet output',
    action='store_true'
  )
  return parser.parse_args(args)
