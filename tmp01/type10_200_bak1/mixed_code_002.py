async def hwc_mixed_002_01(
        self, request_context: Optional[RequestContext]=None,
    ) -> Optional[ResponseReturnValue]:
        """Preprocess the request i.e. call before_request functions.

        Arguments:
            request_context: The request context, optional as Flask
                omits this argument.
        """
        request_ = (request_context or _request_ctx_stack.top).request
        blueprint = request_.blueprint
        processors = self.url_value_preprocessors[None]
        if blueprint is not None:
            processors = chain(processors, self.url_value_preprocessors[blueprint])  # type: ignore
        for processor in processors:
            processor(request.endpoint, request.view_args)

        functions = self.before_request_funcs[None]
        if blueprint is not None:
            functions = chain(functions, self.before_request_funcs[blueprint])  # type: ignore
        for function in functions:
            result = await function()
            if result is not None:
                return result
        return None 

def agc_mixed_002_02(self, node):
        """
        Initialise aliasing default value before visiting.

        Add aliasing values for :
            - Pythonic
            - globals declarations
            - current function arguments
        """
        self.aliasing_default_value = {}
        self.aliasing_default_value.update(self.pythonic_aliasing_default_value)
        self.aliasing_default_value.update(self.globals_aliasing_default_value)
        self.aliasing_default_value.update(self.current_function_arguments_aliasing_default_value)

        self.current_function_arguments_aliasing_default_value = {}
        self.current_function_arguments_aliasing_default_value.update(self.aliasing_default_value)

        self.aliasing_default_value.update(self.current_function_aliasing_default_value)

        self.current_function_aliasing_default_value = {}
        self.current_function_aliasing_default_value.update(self.aliasing_default_value)

        self.aliasing_default_value.update(self.current_function_return_aliasing_default_value)

        self.current_function_return_aliasing_default_value = {}
        self.current_function_return_aliasing_default_value.update(self.aliasing_default_value)

        self.aliasing_default_value.update(self.current_function_arguments_aliasing_default_value)

        self.current_function_arguments_aliasing_default_value = {}
        self.current_function_arguments_aliasing_default_value.update(self.aliasing_default_value)

        self.aliasing_default_value.update(self.current_function_aliasing_default_value)

        self.current_function_aliasing_default_value = {}
        self.current_function_aliasing_default_value.update(self.aliasing_default_value)

        self.aliasing_default_value.update(self.current_function_return_aliasing_default_value)

        self.current_function_return_aliasing_default_value = {}
        self.current_function_return_aliasing_default_value.update(self.aliasing_default_value)

        self.aliasing 

def agc_mixed_002_03(self, cmd="sudo su", pattern="ssword", re_flags=re.IGNORECASE):
        """Attempt to become root."""
        if self.is_root():
            return True
        if not self.is_root():
            self.log.info("Attempting to become root.")
            self.sendline(cmd)
            self.expect(pattern, timeout=10)
            self.sendline(self.password)
            self.expect(self.prompt)
            if self.is_root():
                self.log.info("Successfully became root.")
                return True
            else:
                self.log.error("Failed to become root.")
                return False 

def hwc_mixed_002_04(self, dimmer):
        """Set final dimmer value for task."""
        command = {
            ATTR_START_ACTION: {
                    ATTR_DEVICE_STATE: self.state,
                    ROOT_START_ACTION: [{
                        ATTR_ID: self.raw[ATTR_ID],
                        ATTR_LIGHT_DIMMER: dimmer,
                        ATTR_TRANSITION_TIME: self.raw[ATTR_TRANSITION_TIME]
                    }, self.devices_dict]
                }
            }
        return self.set_values(command) 

def agc_mixed_002_05(dist, _, value):
    # type: (setuptools.dist.Distribution, str, bool) -> None
    """Add autodetected commands as entry points.

    Args:
        dist: The distutils Distribution object for the project being
            installed.
        _: The keyword used in the setup function. Unused.
        value: The value set to the keyword in the setup function. If the value
            is not True, this function will do nothing.
    """
    if not isinstance(value, bool):
        raise TypeError(
            "The keyword 'setup_keyword' must be set to True or False, not {!r}".format(value)
        )

    if value:
        # Add the autodetected commands as entry points.
        for command in get_commands():
            dist.entry_points.append(
                setuptools.dist.Distribution.EntryPoint(
                    "console_scripts",
                    "{} = {}".format(command.name, command.module_name),
                    dist=dist.get_name(),
                )
            ) 

def hwc_mixed_002_06(template):
    """A generator which yields Token instances"""
    upto = 0
    lineno = 0

    for m in tag_re.finditer(template):

        start, end = m.span()
        lineno = template.count('\n', 0, start) + 1  # Humans count from 1
        # If there's a gap between our start and the end of the last match,
        # there's a Text node between.
        if upto < start:
            yield Token(TokenType.text, template[upto:start], lineno)
        upto = end

        mode = m.lastgroup
        content = m.group(mode)
        yield Token(TokenType[mode], content, lineno)

    # if the last match ended before the end of the source, we have a tail Text
    # node.
    if upto < len(template):
        yield Token(TokenType.text, template[upto:], lineno)
