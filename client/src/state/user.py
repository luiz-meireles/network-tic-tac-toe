from statemachine import StateMachine, State


class UserStateMachine(StateMachine):
    logged_out = State("LoggedOut", initial=True)
    logged = State("Logged")
    playing_game = State("Playing")
    waiting_game_instruction = State("WaitingGame")

    login_success = logged_out.to(logged)
    log_off = logged.to(logged_out)
    game_init = logged.to(playing_game)
    game_end = playing_game.to(logged)
    waiting = playing_game.to(waiting_game_instruction)
    ready = waiting_game_instruction.to(playing_game)
