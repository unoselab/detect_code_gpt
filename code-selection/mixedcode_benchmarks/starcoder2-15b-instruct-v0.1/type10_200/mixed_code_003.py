def agc_mixed_003_01(stmt,
                with_prefixes=False,
                prefix_onchange=False,
                prefix_to_module=False,
                resolve_top_prefix_to_module=False):
    """Returns the XPath path of the node.
    with_prefixes indicates whether or not to prefix every node.

    prefix_onchange modifies the behavior of with_prefixes and
      only adds prefixes when the prefix changes mid-XPath.

    prefix_to_module replaces prefixes with the module name of the prefix.

    resolve_top_prefix_to_module resolves the module-level prefix
      to the module name.

    Prefixes may be included in the path if the prefix changes mid-path.
    """
    path = []
    prefix = None
    for node in stmt.xpath:
        if with_prefixes or prefix_onchange:
            if prefix!= node.prefix:
                prefix = node.prefix
                if prefix_to_module:
                    prefix = node.module_name
                path.append(prefix + ':' + node.name)
            else:
                path.append(node.name)
        else:
            path.append(node.name)
    if resolve_top_prefix_to_module:
        path[0] = node.module_name + ':' + path[0]
    return '/' + '/'.join(path) 

def agc_mixed_003_02(content, force_single_line, sort_key):
    """
    'sort_key' 参数只在 dict 模式时有效
    'sort_key' parameter only available in 'dict' mode
    """

    if force_single_line:
        print(content)
    else:
        if isinstance(content, dict):
            if sort_key:
                for key in sorted(content.keys(), key=sort_key):
                    print(f"{key}: {content[key]}")
            else:
                for key in sorted(content.keys()):
                    print(f"{key}: {content[key]}")
        elif isinstance(content, list):
            for item in content:
                print(item)
        else:
            print(content) 

def hwc_mixed_003_03(self, expression):
        """Expands logical constructions."""
        self.logger.debug("expand : expression %s", str(expression))
        if not is_string(expression):
            return expression

        result = self._pattern.sub(lambda var: str(self._variables[var.group(1)]), expression)

        result = result.strip()
        self.logger.debug('expand : %s - result : %s', expression, result)

        if is_number(result):
            if result.isdigit():
                self.logger.debug('     expand is integer !!!')
                return int(result)
            else:
                self.logger.debug('     expand is float !!!')
                return float(result)
        return result 

def hwc_mixed_003_04(self, courseid):  # pylint: disable=arguments-differ
        """ POST request """
        course, __ = self.get_course_and_check_rights(courseid)
        data = web.input(task=[])

        if "task" in data:
            # Change tasks order
            for index, taskid in enumerate(data["task"]):
                try:
                    task = self.task_factory.get_task_descriptor_content(courseid, taskid)
                    task["order"] = index
                    self.task_factory.update_task_descriptor_content(courseid, taskid, task)
                except:
                    pass

        return self.page(course) 

def agc_mixed_003_05(self, uid, channel=None):
        """Get user access

        :param uid: user number [1:16]
        :param channel: number [1:7]

        :return:
        channel_info:
            max_user_count = maximum number of user IDs on this channel
            enabled_users = count of User ID slots presently in use
            users_with_fixed_names = count of user IDs with fixed names

        access:
            callback
            link_auth
            ipmi_msg
            privilege_level: [reserved, callback, user,
                              operatorm administrator, proprietary, no_access]
        """
        # user access available during call-in or callback direct connection
        if not 1 <= uid <= 16:
            raise ValueError("User ID must be between 1 and 16")
        if channel is not None and not 1 <= channel <= 7:
            raise ValueError("Channel must be between 1 and 7")
        if channel is None:
            channel_info = self.get_channel_info()
            enabled_users = self.get_enabled_users()
            users_with_fixed_names = self.get_users_with_fixed_names()
        else:
            channel_info = self.get_channel_info(channel)
            enabled_users = self.get_enabled_users(channel)
            users_with_fixed_names = self.get_users_with_fixed_names(channel)
        access = self.get_user_access(uid, channel)
        return channel_info, enabled_users, users_with_fixed_names, access 

def hwc_mixed_003_06(params, x, tx, T):
        warnings.simplefilter(action="ignore", category=FutureWarning)

        """Log likelihood for optimizer."""
        alpha, beta, gamma, delta = params

        betaln_ab = betaln(alpha, beta)
        betaln_gd = betaln(gamma, delta)

        A = betaln(alpha + x, beta + T - x) - betaln_ab + betaln(gamma, delta + T) - betaln_gd

        B = 1e-15 * np.ones_like(T)
        recency_T = T - tx - 1

        for j in np.arange(recency_T.max() + 1):
            ix = recency_T >= j
            B = B + ix * betaf(alpha + x, beta + tx - x + j) * betaf(gamma + 1, delta + tx + j)

        B = log(B) - betaln_gd - betaln_ab
        return logaddexp(A, B)
