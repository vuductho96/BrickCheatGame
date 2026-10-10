from unittest.mock import Mock
import play_until_loss as monitor


def setup_monitor(monkeypatch,tmp_path,statuses,states):
    statuses,states=iter(statuses),iter(states)
    monkeypatch.setattr(monitor,'LOG',tmp_path)
    monkeypatch.setattr(monitor,'get',lambda path:next(statuses) if path=='/api/auto' else next(states))
    for name in ('append','save_failures','finish','post'):
        monkeypatch.setattr(monitor,name,Mock())
    monkeypatch.setattr(monitor.time,'sleep',lambda _:None)


def stopped(message):return {'active':False,'message':message}


def test_game_over_ends_session_without_starting_another_game(monkeypatch,tmp_path):
    setup_monitor(monkeypatch,tmp_path,[stopped('Ván đã thua')],[{'phase':'game_over'}])
    monitor.run()
    monitor.finish.assert_called_once_with('game_over',True)
    monitor.post.assert_not_called()


def test_manual_stop_is_respected_even_on_a_playable_board(monkeypatch,tmp_path):
    setup_monitor(monkeypatch,tmp_path,[stopped('Đã dừng Auto')],[{'phase':'playing','state_id':'a'}])
    monitor.run()
    monitor.finish.assert_called_once_with('Đã dừng Auto',False)
    monitor.post.assert_not_called()


def test_restart_requires_three_identical_confirmed_states(monkeypatch,tmp_path):
    failure=stopped('Thả lệch ô dự kiến; Auto dừng để tránh làm hỏng bàn')
    states=[{'phase':'playing','state_id':sid} for sid in ('a','b','b','b')]+[{'phase':'game_over'}]
    setup_monitor(monkeypatch,tmp_path,[failure]*4+[stopped('Ván đã thua')],states)
    monitor.run()
    monitor.post.assert_called_once_with('start')
    monitor.finish.assert_called_once_with('game_over',True)


def test_nonplaying_screens_cannot_trigger_restart(monkeypatch,tmp_path):
    failure=stopped('Chưa xác minh bàn và khay sau hủy kéo; Auto đã dừng')
    setup_monitor(monkeypatch,tmp_path,[failure]*3+[stopped('Đã dừng Auto')],
        [{'phase':'waiting_for_pieces'}]*3+[{'phase':'playing','state_id':'a'}])
    monitor.run()
    monitor.post.assert_not_called()
