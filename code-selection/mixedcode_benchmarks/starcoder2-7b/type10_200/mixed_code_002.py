def agc_mixed_002_01(self, release):
        """Copy the workfile of the given release to the releasefile location

        This is inteded to be used in a action unit.

        :param release: the release with the release and workfile
        :type release: :class:`Release`
        :returns: an action status
        :rtype: :class:`ActionStatus`
        :raises: None
        """
        if not release.releasefile:
            return ActionStatus(ActionStatus.ERROR, "No releasefile defined")
        if not release.workfile:
            return ActionStatus(ActionStatus.ERROR, "No workfile defined")
        if not os.path.exists(release.workfile):
            return ActionStatus(ActionStatus.ERROR, "Workfile does not exist")
        if not os.path.exists(os.path.dirname(release.releasefile)):
            return ActionStatus(ActionStatus.ERROR, "Releasefile directory does not exist")
        if os.path.exists(release.releasefile):
            return ActionStatus(ActionStatus.ERROR, "Releasefile already exists")
        try:
            shutil.copy(release.workfile, release.releasefile)
        except Exception as e:
            return ActionStatus(ActionStatus.ERROR, "Error copying workfile to releasefile: %s" % str(e))
        return ActionStatus(ActionStatus.SUCCESS, "Copied workfile to releasefile") 

def hwc_mixed_002_02(self, args):
        """remove an output"""
        device = args[0]
        for i in range(len(self.mpstate.mav_outputs)):
            conn = self.mpstate.mav_outputs[i]
            if str(i) == device or conn.address == device:
                print("Removing output %s" % conn.address)
                try:
                    mp_util.child_fd_list_add(conn.port.fileno())
                except Exception:
                    pass
                conn.close()
                self.mpstate.mav_outputs.pop(i)
                return 

def agc_mixed_002_03(cllable = None, call_args = None, clss = None, caller_level = 0):
    """Can be called from within a function or method to apply typechecking to
    the arguments that were passed in by the caller. Checking is applied w.r.t.
    type hints of the function or method hosting the call to check_argument_types.
    """
    if cllable is None:
        cllable = sys._getframe(caller_level + 1).f_code.co_name
    if call_args is None:
        call_args = sys._getframe(caller_level + 1).f_locals
    if clss is None:
        clss = sys._getframe(caller_level + 1).f_code.co_filename
    if not hasattr(clss, cllable):
        raise Exception("Function or method {} not found in class {}".format(cllable, clss))
    func = getattr(clss, cllable)
    if not hasattr(func, "__annotations__"):
        raise Exception("Function or method {} has no annotations".format(cllable))
    for arg, arg_type in func.__annotations__.items():
        if arg not in call_args:
            raise Exception("Function or method {} has no argument named {}".format(cllable, arg))
        if not isinstance(call_args[arg], arg_type):
            raise Exception("Function or method {} argument {} has type {} but was passed {}".format(cllable, arg, arg_type, type(call_args[arg]))) 

def hwc_mixed_002_04(parent, xpath):
    """ Perform an XPath on an element and indicate if we need to loop over it to find something

    :param parent: XML Node on which to perform XPath
    :param xpath: XPath to run
    :return: (Result, Need to loop Indicator)
    """
    loop = False
    if xpath.startswith(".//"):
        result = parent.xpath(
            xpath.replace(".//", "./", 1),
            namespaces=XPATH_NAMESPACES
        )
        if len(result) == 0:
            result = parent.xpath(
                "*[{}]".format(xpath),
                namespaces=XPATH_NAMESPACES
            )
            loop = True
    else:
        result = parent.xpath(
            xpath,
            namespaces=XPATH_NAMESPACES
        )
    return result[0], loop 

def agc_mixed_002_05(
    obj,
    level_keys,
    v_level_indexes,
    h_level_indexes,
    v_level_sort_keys=None,
    h_level_sort_keys=None,
):
    """
    Args:
        v_level_indexes: A sequence of level indexes.
        h_level_indexes: A sequence of level indexes.
    """
    if v_level_sort_keys is None:
        v_level_sort_keys = [None] * len(v_level_indexes)
    if h_level_sort_keys is None:
        h_level_sort_keys = [None] * len(h_level_indexes)

    v_level_indexes = list(v_level_indexes)
    h_level_indexes = list(h_level_indexes)

    v_level_indexes.reverse()
    h_level_indexes.reverse()

    v_level_sort_keys.reverse()
    h_level_sort_keys.reverse()

    v_level_indexes_len = len(v_level_indexes)
    h_level_indexes_len = len(h_level_indexes)

    v_level_indexes_len_minus_one = v_level_indexes_len - 1
    h_level_indexes_len_minus_one = h_level_indexes_len - 1

    v_level_indexes_len_minus_two = v_level_indexes_len - 2
    h_level_indexes_len_minus_two = h_level_indexes_len - 2

    v_level_indexes_len_minus_three = v_level_indexes_len - 3
    h_level_indexes_len_minus_three = h_level_indexes_len - 3

    v_level_indexes_len_minus_four = v_level_indexes_len - 4
    h_level_indexes_len_minus_four = h_level_indexes_len - 4

    v_level_indexes_len_minus_five = v_level_indexes_len - 5
    h_level_indexes_len_minus_five = h_level_indexes_len - 5

    v_level_indexes_len_minus_six = v_level_indexes_len - 6
    h_level_indexes_len_minus_six = h_level_indexes_len - 6

    v_level_indexes_len_minus_seven = v_level_indexes_len - 7
    h_level_indexes_len_minus_seven = h_level_indexes_len - 7

    v_level_indexes_len_minus_eight = v_level_indexes 

def hwc_mixed_002_06(self, sample):
        """Updates the Preserver and the Date Preserved with the values provided
        in the request. If neither Preserver nor DatePreserved are present in
        the request, returns False
        """
        if sample.getPreserver() and sample.getDatePreserved():
            # Preserver and Date Preserved already set. This is correct
            return True
        preserver = self.get_form_value("Preserver", sample,
                                        sample.getPreserver())
        preserved = self.get_form_value("getDatePreserved",
                                        sample.getDatePreserved())
        if not all([preserver, preserved]):
            return False
        sample.setPreserver(preserver)
        sample.setDatePreserver(DateTime(preserved))
        return True
