def agc_mixed_003_01(self, course_id, asset_id=None, asset_type=None):
        """
        Get module item sequence.

        Given an asset in a course, find the ModuleItem it belongs to, and also the previous and next Module Items
        in the course sequence.
        """
        if asset_type is None:
            asset_type = self.get_asset_type(asset_id)

        if asset_type == 'course':
            return self.get_course_sequence(course_id)
        elif asset_type =='module':
            return self.get_module_sequence(course_id, asset_id)
        elif asset_type =='module_item':
            return self.get_module_item_sequence(course_id, asset_id)
        else:
            raise Exception('Unknown asset type: %s' % asset_type) 

def agc_mixed_003_02(
        address,
        web3,
        fn_identifier=None,
        transaction=None,
        contract_abi=None,
        fn_abi=None,
        *args,
        **kwargs):
    """Estimates gas cost a function call would take.

    Don't call this directly, instead use :meth:`Contract.estimateGas`
    on your contract instance.
    """
    if fn_identifier is None:
        fn_identifier = (fn_abi, args, kwargs)
    if transaction is None:
        transaction = {}
    if contract_abi is None:
        contract_abi = get_contract_abi(address, web3)
    if fn_abi is None:
        fn_abi = get_function_abi(contract_abi, fn_identifier)
    return estimate_gas_for_function_call(
        address,
        web3,
        fn_abi,
        transaction,
        *args,
        **kwargs) 

def hwc_mixed_003_03(role_name, sr_entry):
  """
  If 'aws_managed_policies' key lists the names of AWS managed policies to bind to the role,
  attach them to the role
  Args:
    role_name: name of the role to attach the policies to
    sr_entry: service registry entry
  """
  service_type = sr_entry['type']
  if not (service_type in SERVICE_TYPE_ROLE and "aws_managed_policies" in sr_entry):
    print_if_verbose("not eligible for policies; service_type: {} is not valid for policies "
                     "or no 'aws_managed_policies' key in service registry for this role".format(service_type))
    return

  for policy_name in sr_entry['aws_managed_policies']:
    print_if_verbose("loading policy: {} for role: {}".format(policy_name, role_name))

    if CONTEXT.commit:
      try:
        CLIENTS["iam"].attach_role_policy(RoleName=role_name, PolicyArn='arn:aws:iam::aws:policy/' + policy_name)
      except:
        fail("Exception putting policy: {} onto role: {}".format(policy_name, role_name), sys.exc_info()) 

def agc_mixed_003_04(self, obj):
        """At first create schemas without 'AllOf'
        :param obj:
        :return: None
        """
        for key, value in obj.items():
            if key == 'definitions':
                for definition_name, definition in value.items():
                    self._fill_schemas_from_definitions(definition)
                    self.schemas[definition_name] = Schema(definition_name, definition)
            else:
                self.schemas[key] = Schema(key, value) 

def hwc_mixed_003_05(starts, ends, cur_block, rec_num):   # @NoSelf
        """
        Finds the block that rec_num is in if it is found. Otherwise it returns -1.
        It also returns the block that has the physical data either at or
        preceeding the rec_num.
        It could be -1 if the preceeding block does not exists.
        """
        total = len(starts)
        if (cur_block == -1):
            cur_block = 0
        for x in range(cur_block, total):
            if (starts[x] <= rec_num and ends[x] >= rec_num):
                return x, x
            if (starts[x] > rec_num):
                break
        return -1, x-1 

def hwc_mixed_003_06():
    """
    Opens the topic-keyword map resource file and returns the corresponding python dictionary.

    - Input:  - file_path: The path pointing to the topic-keyword map resource file.

    - Output: - topic_set: A topic to keyword python dictionary.
    """
    topic_keyword_dictionary = dict()
    file_row_gen = get_file_row_generator(get_package_path() + "/twitter/res/topics/topic_keyword_mapping" + ".txt",
                                          ",",
                                          "utf-8")
    for file_row in file_row_gen:
        topic_keyword_dictionary[file_row[0]] = set([keyword for keyword in file_row[1:]])

    return topic_keyword_dictionary
