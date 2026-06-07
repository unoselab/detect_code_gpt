def agc_mixed_003_01(self):
        """Returns an array of nodes in the tree that have balanced subtrees beneath them,
        moving from left to right.
        """
        result = []
        def dfs(node):
            if not node:
                return 0
            left_height = dfs(node.left)
            right_height = dfs(node.right)
            if abs(left_height - right_height) <= 1:
                result.append(node)
            return max(left_height, right_height) + 1
        dfs(self)
        return result 

def agc_mixed_003_02(self, name, course_id, hidden=None, lock_at=None, locked=None, parent_folder_id=None, parent_folder_path=None, position=None, unlock_at=None):
        """
        Create folder.

        Creates a folder in the specified context
        """
        folder_data = {
            'name': name,
            'course_id': course_id,
            'hidden': hidden,
            'lock_at': lock_at,
            'locked': locked,
            'parent_folder_id': parent_folder_id,
            'parent_folder_path': parent_folder_path,
            'position': position,
            'unlock_at': unlock_at
        }
        return self.post('folders', data=folder_data) 

def hwc_mixed_003_03(cls, alias, cert):
        """
        Helper function to create a new TrustedCertEntry.

        :param str alias: The alias for the Trusted Cert Entry
        :param str certs: The certificate, as a byte string.

        :returns: A loaded :class:`TrustedCertEntry` instance, ready
          to be placed in a keystore.
        """
        timestamp = int(time.time()) * 1000

        tke = cls(timestamp = timestamp,
                               # Alias must be lower case or it will corrupt the keystore for Java Keytool and Keytool Explorer
                               alias = alias.lower(),
                               cert = cert)
        return tke 

def hwc_mixed_003_04(self, pattern: Union[Pattern, FlatTerm], final_label: T=None) -> int:
        """Add a pattern to the discrimination net.

        Args:
            pattern:
                The pattern which is added to the DiscriminationNet. If an expression is given, it will be converted to
                a `FlatTerm` for internal processing. You can also pass a `FlatTerm` directly.
            final_label:
                A label that is returned if the pattern matches when using :meth:`match`. This will default to the
                pattern itself.

        Returns:
            The index of the newly added pattern. This is used internally to later to get the pattern and its final
            label once a match is found.
        """
        index = len(self._patterns)
        self._patterns.append((pattern, final_label))
        flatterm = FlatTerm(pattern.expression) if not isinstance(pattern, FlatTerm) else pattern
        if flatterm.is_syntactic or len(flatterm) == 1:
            net = self._generate_syntactic_net(flatterm, index)
        else:
            net = self._generate_net(flatterm, index)

        if self._root:
            self._root = self._product_net(self._root, net)
        else:
            self._root = net
        return index 

def hwc_mixed_003_05(operator):
    """
    Allowed input/output patterns are
        1. [N, C, H, W] ---> [N, C, H', W']
        2. [N, C, H, W],  shape-ref [N', C', H', W'] ---> [N, C, H', W']
    """
    check_input_and_output_numbers(operator, input_count_range=[1, 2], output_count_range=1)
    check_input_and_output_types(operator, good_input_types=[FloatTensorType])

    output_shape = copy.deepcopy(operator.inputs[0].type.shape)

    params = operator.raw_operator.crop
    if len(operator.inputs) == 1:
        if len(params.cropAmounts.borderAmounts) > 0:
            output_shape[2] -= params.cropAmounts.borderAmounts[0].startEdgeSize
            output_shape[2] -= params.cropAmounts.borderAmounts[0].endEdgeSize
            output_shape[3] -= params.cropAmounts.borderAmounts[1].startEdgeSize
            output_shape[3] -= params.cropAmounts.borderAmounts[1].endEdgeSize
    elif len(operator.inputs) == 2:
        output_shape[2] = operator.inputs[1].type.shape[2]
        output_shape[3] = operator.inputs[1].type.shape[3]
    else:
        raise RuntimeError('Too many inputs for Crop operator')

    operator.outputs[0].type.shape = output_shape 

def agc_mixed_003_06(state, host, name, present=True, force=False):
    """
    Load/unload kernel modules.

    + name: name of the module to manage
    + present: whether the module should be loaded or not
    + force: whether to force any add/remove modules
    """

    if state == 'present' and not present:
        return {
            'name': name,
           'state': 'absent'
        }
    elif state == 'absent' and present:
        return {
            'name': name,
           'state': 'present'
        }
    else:
        return {
            'name': name,
           'state': state
        }
