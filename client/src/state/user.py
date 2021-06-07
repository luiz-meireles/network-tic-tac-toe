from statemachine import StateMachine, State


class UserMachine(StateMachine):
    logged_out = State("LoggedOut", initial=True)
    logged = State("Logged")

    login_fail = logged_out.to(logged_out)
    login_success = logged_out.to(logged)
    log_off = logged.to(logged_out)
