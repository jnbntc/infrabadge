"""Shared, explicit USB scope for a new run; never touches hardware."""
def authorization(mode):
    if mode=='load_setup':
        return {'app_writes':1,'setups':1,'exports':1,'restore_firmware':False}
    if mode=='setup_existing':
        return {'app_writes':0,'setups':1,'exports':1,'restore_firmware':False,'usb_resets':1}
    raise ValueError('unsupported_execution_mode')
