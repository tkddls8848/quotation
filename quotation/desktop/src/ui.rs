//! 창. 판단은 여기 없다 — 변환 순서는 `convert`, 경로 정책은 `paths` 가 갖는다.
//!
//! Tkinter 판을 그대로 옮겼다. 달라진 것은 둘이다.
//!   - 상태를 알리던 작은 색 점 대신 진행 막대 자체가 색으로 말한다.
//!     Windows 가 막대에 정상·실패 색을 그려 주므로 따로 그릴 이유가 없다.
//!   - 창 크기를 고정했다. 늘어날 칸이 없는 화면이다.
use std::cell::RefCell;
use std::collections::VecDeque;
use std::ffi::OsStr;
use std::os::windows::ffi::OsStrExt;
use std::path::{Path, PathBuf};
use std::ptr::null_mut;
use std::rc::Rc;
use std::sync::{Arc, Mutex};
use std::thread;

use native_windows_gui as nwg;
use quotation_core::modes::Mode;

use crate::config::{self, Config};
use crate::convert;
use crate::paths;

pub const TITLE: &str = "견적서 작성기";
const READY: &str = "변환할 XML 파일을 선택하십시오.";
const PICKED: &str = "<변환> 버튼을 누르면 견적서 변환작업을 시작합니다.";

const MODES: [Mode; 2] = [Mode::Unix, Mode::Integrated];
const MODE_LABELS: [&str; 2] = ["IBM", "Lenovo x86"];

/// 일꾼 실이 창에 보내는 것.
enum Report {
    Progress(u8, String),
    Done(Box<convert::Outcome>),
    Failed(String),
}

struct Ui {
    window: nwg::Window,
    _tips: nwg::Tooltip,
    /// 글자만 보여 주는 것들. nwg 컨트롤은 drop 되면 핸들이 사라지므로 붙잡아 둔다.
    _labels: Vec<nwg::Label>,
    path_input: nwg::TextInput,
    browse: nwg::Button,
    open_result: nwg::CheckBox,
    template_open: [nwg::Button; 2],
    status: nwg::Label,
    percent: nwg::Label,
    progress: nwg::ProgressBar,
    convert_button: nwg::Button,
    quit: nwg::Button,
    dialog: nwg::FileDialog,
    notice: nwg::Notice,
}

struct State {
    config: Config,
    busy: bool,
    templates: [PathBuf; 2],
    reports: Arc<Mutex<VecDeque<Report>>>,
}

type Shared = Rc<RefCell<State>>;

pub fn run(prefill: Option<PathBuf>) -> Result<(), nwg::NwgError> {
    nwg::init()?;
    // 한글 화면이다. 시스템 한글 UI 글꼴을 그대로 쓴다.
    let _ = nwg::Font::set_global_family("Malgun Gothic");

    // 글꼴은 핸들일 뿐이라 drop 되어도 사라지지 않는다. 라벨·단추와 다른 점이다.
    let mut heading = nwg::Font::default();
    nwg::Font::builder()
        .family("Malgun Gothic")
        .size(20)
        .weight(700)
        .build(&mut heading)?;
    let mut body = nwg::Font::default();
    nwg::Font::builder()
        .family("Malgun Gothic")
        .size(15)
        .build(&mut body)?;
    let mut mono = nwg::Font::default();
    nwg::Font::builder()
        .family("Consolas")
        .size(13)
        .build(&mut mono)?;

    let mut window = nwg::Window::default();
    nwg::Window::builder()
        .size((560, 292))
        .position((260, 180))
        .title(TITLE)
        .flags(nwg::WindowFlags::WINDOW | nwg::WindowFlags::VISIBLE)
        .build(&mut window)?;

    let text = |content: &str,
                position: (i32, i32),
                size: (u32, u32),
                font: Option<&nwg::Font>|
     -> Result<nwg::Label, nwg::NwgError> {
        let mut control = nwg::Label::default();
        nwg::Label::builder()
            .text(content)
            .position(position)
            .size((size.0 as i32, size.1 as i32))
            .font(font)
            .parent(&window)
            .build(&mut control)?;
        Ok(control)
    };

    // 화면은 한 가지 일만 한다 — XML 을 고르고, 변환한다. 2005년 판이 그랬듯
    // 고르는 칸과 주 단추를 앞에 두고, 나머지는 뒤로 물린다. 제목은 창틀이
    // 이미 말하므로 본문에 다시 적지 않는다.
    let mut labels = vec![text("XML 파일", (16, 18), (120, 20), Some(&body))?];

    let mut path_input = nwg::TextInput::default();
    nwg::TextInput::builder()
        .text(
            &prefill
                .as_ref()
                .map(|path| path.display().to_string())
                .unwrap_or_default(),
        )
        .position((16, 40))
        .size((404, 28))
        .font(Some(&mono))
        .parent(&window)
        .build(&mut path_input)?;

    let mut browse = nwg::Button::default();
    nwg::Button::builder()
        .font(Some(&body))
        .text("열기")
        .position((432, 39))
        .size((112, 30))
        .parent(&window)
        .build(&mut browse)?;

    labels.push(text(
        "eConfig 에서 Export 한 XML 을 고르면 같은 폴더에 견적서를 만듭니다.",
        (16, 78),
        (528, 20),
        Some(&body),
    )?);
    labels.push(text(
        "IBM 과 Lenovo x86 은 문서를 보고 가려 씁니다.",
        (16, 98),
        (528, 20),
        Some(&body),
    )?);

    let mut open_result = nwg::CheckBox::default();
    nwg::CheckBox::builder()
        .font(Some(&body))
        .text("완료 후 견적서 열기")
        .position((16, 128))
        .size((240, 24))
        .parent(&window)
        .build(&mut open_result)?;

    let status = text(READY, (16, 168), (400, 20), Some(&body))?;
    let percent = text("0%", (462, 168), (82, 20), Some(&body))?;

    let mut progress = nwg::ProgressBar::default();
    nwg::ProgressBar::builder()
        .range(0..100)
        .position((16, 192))
        .size((528, 14))
        .parent(&window)
        .build(&mut progress)?;

    // 견적서 번호와 담당자 이름은 템플릿에서 고친다. 자주 하는 일이 아니므로
    // 경로를 늘어놓지 않고 작은 단추 둘만 둔다 — 전체 경로는 풍선말이 말한다.
    labels.push(text("템플릿", (16, 234), (48, 20), Some(&body))?);
    let mut templates = [PathBuf::new(), PathBuf::new()];
    let mut template_open: Vec<nwg::Button> = Vec::new();
    for (index, mode) in MODES.iter().enumerate() {
        templates[index] = paths::template_path(*mode)
            .unwrap_or_else(|_| PathBuf::from(paths::template_name(*mode)));
        let mut button = nwg::Button::default();
        nwg::Button::builder()
            .font(Some(&body))
            .text(MODE_LABELS[index])
            .position((72 + (index as i32) * 96, 230))
            .size((88, 28))
            .parent(&window)
            .build(&mut button)?;
        template_open.push(button);
    }

    let mut convert_button = nwg::Button::default();
    nwg::Button::builder()
        .font(Some(&body))
        .text("변환")
        .position((348, 228))
        .size((92, 32))
        .parent(&window)
        .build(&mut convert_button)?;

    let mut quit = nwg::Button::default();
    nwg::Button::builder()
        .font(Some(&body))
        .text("종료")
        .position((452, 228))
        .size((92, 32))
        .parent(&window)
        .build(&mut quit)?;

    let mut tips = nwg::Tooltip::default();
    nwg::Tooltip::builder()
        .register(&convert_button, "Enter 로도 됩니다")
        .register(&template_open[0], &templates[0].display().to_string())
        .register(&template_open[1], &templates[1].display().to_string())
        .build(&mut tips)?;

    let mut dialog = nwg::FileDialog::default();
    nwg::FileDialog::builder()
        .title("XML파일 선택")
        .action(nwg::FileDialogAction::Open)
        .filters("XML 파일(*.xml)|모든 파일(*.*)")
        .build(&mut dialog)?;

    let mut notice = nwg::Notice::default();
    nwg::Notice::builder().parent(&window).build(&mut notice)?;

    let config = config::load();
    if config.open_result_when_done {
        open_result.set_check_state(nwg::CheckBoxState::Checked);
    }
    if prefill.is_some() {
        status.set_text(PICKED);
    }

    let second = template_open.pop().expect("템플릿 단추 둘");
    let first = template_open.pop().expect("템플릿 단추 둘");
    let ui = Rc::new(Ui {
        window,
        _tips: tips,
        _labels: labels,
        path_input,
        browse,
        open_result,
        template_open: [first, second],
        status,
        percent,
        progress,
        convert_button,
        quit,
        dialog,
        notice,
    });
    let state = Rc::new(RefCell::new(State {
        config,
        busy: false,
        templates,
        reports: Arc::new(Mutex::new(VecDeque::new())),
    }));

    let handler = {
        let ui = ui.clone();
        let state = state.clone();
        nwg::full_bind_event_handler(&ui.window.handle.clone(), move |event, _data, handle| {
            match event {
                nwg::Event::OnWindowClose => nwg::stop_thread_dispatch(),
                nwg::Event::OnButtonClick => {
                    if handle == ui.quit.handle {
                        nwg::stop_thread_dispatch();
                    } else if handle == ui.browse.handle {
                        pick(&ui, &state);
                    } else if handle == ui.convert_button.handle {
                        start(&ui, &state);
                    } else if handle == ui.template_open[0].handle {
                        let path = state.borrow().templates[0].clone();
                        open_with_default_app(&ui, &path);
                    } else if handle == ui.template_open[1].handle {
                        let path = state.borrow().templates[1].clone();
                        open_with_default_app(&ui, &path);
                    }
                }
                nwg::Event::OnKeyEnter => start(&ui, &state),
                nwg::Event::OnNotice => drain(&ui, &state),
                _ => {}
            }
        })
    };

    nwg::dispatch_thread_events();
    nwg::unbind_event_handler(&handler);
    Ok(())
}

fn pick(ui: &Ui, state: &Shared) {
    let last = state.borrow().config.last_input_dir.clone();
    if !last.is_empty() {
        let _ = ui.dialog.set_default_folder(&last);
    }
    if ui.dialog.run(Some(&ui.window)) {
        if let Ok(chosen) = ui.dialog.get_selected_item() {
            ui.path_input.set_text(&chosen.to_string_lossy());
            ui.status.set_text(PICKED);
            ui.progress.set_pos(0);
            ui.progress.set_state(nwg::ProgressBarState::Normal);
            ui.percent.set_text("0%");
        }
    }
}

fn start(ui: &Ui, state: &Shared) {
    if state.borrow().busy {
        return;
    }
    let raw = ui.path_input.text().trim().to_owned();
    if raw.is_empty() {
        nwg::modal_info_message(&ui.window, TITLE, "작업할 파일을 선택하세요.");
        return;
    }
    let xml = PathBuf::from(&raw);
    if !xml.is_file() {
        nwg::modal_error_message(
            &ui.window,
            TITLE,
            &format!("파일을 찾을 수 없습니다.\n{raw}"),
        );
        return;
    }

    let target = convert::output_path_for(&xml);
    if target.exists() {
        let name = target
            .file_name()
            .map(|name| name.to_string_lossy().into_owned())
            .unwrap_or_default();
        let answer = nwg::modal_message(
            &ui.window,
            &nwg::MessageParams {
                title: TITLE,
                content: &format!("이미 있는 파일을 덮어씁니다.\n\n{name}\n\n계속할까요?"),
                buttons: nwg::MessageButtons::YesNo,
                icons: nwg::MessageIcons::Question,
            },
        );
        if answer != nwg::MessageChoice::Yes {
            return;
        }
    }

    set_busy(ui, state, true);
    ui.progress.set_state(nwg::ProgressBarState::Normal);

    let reports = state.borrow().reports.clone();
    let sender = ui.notice.sender();
    thread::spawn(move || {
        let push = |report: Report| {
            if let Ok(mut queue) = reports.lock() {
                queue.push_back(report);
            }
            sender.notice();
        };
        let outcome = convert::run(
            &xml,
            convert::today(),
            &paths::template_path,
            &|percent, message| push(Report::Progress(percent, message.to_owned())),
        );
        match outcome {
            Ok(result) => push(Report::Done(Box::new(result))),
            Err(failure) => push(Report::Failed(failure.message())),
        }
    });
}

fn drain(ui: &Ui, state: &Shared) {
    loop {
        let report = {
            let borrowed = state.borrow();
            let mut queue = match borrowed.reports.lock() {
                Ok(queue) => queue,
                Err(_) => return,
            };
            match queue.pop_front() {
                Some(report) => report,
                None => return,
            }
        };
        match report {
            Report::Progress(percent, message) => {
                ui.progress.set_pos(u32::from(percent));
                ui.percent.set_text(&format!("{percent}%"));
                ui.status.set_text(&message);
            }
            Report::Done(outcome) => finish(ui, state, *outcome),
            Report::Failed(message) => {
                set_busy(ui, state, false);
                ui.progress.set_pos(0);
                ui.progress.set_state(nwg::ProgressBarState::Error);
                ui.percent.set_text("0%");
                ui.status.set_text("변환에 실패했습니다.");
                nwg::modal_error_message(&ui.window, TITLE, &message);
            }
        }
    }
}

fn finish(ui: &Ui, state: &Shared, outcome: convert::Outcome) {
    set_busy(ui, state, false);
    ui.progress.set_pos(100);
    ui.percent.set_text("100%");
    ui.status.set_text(&format!(
        "견적서작성을 완료하였습니다.  장비군 {}개 · {:.1}초",
        outcome.group_count, outcome.elapsed
    ));

    let open_now = ui.open_result.check_state() == nwg::CheckBoxState::Checked;
    {
        let mut borrowed = state.borrow_mut();
        let input = PathBuf::from(ui.path_input.text());
        borrowed.config.remember(&input);
        borrowed.config.open_result_when_done = open_now;
        config::save(&borrowed.config);
    }

    // 알림창은 띄우지 않는다. 만든 견적서를 바로 연다.
    if open_now {
        open_with_default_app(ui, &outcome.output);
    }
}

fn set_busy(ui: &Ui, state: &Shared, busy: bool) {
    state.borrow_mut().busy = busy;
    ui.convert_button.set_enabled(!busy);
    ui.browse.set_enabled(!busy);
}

/// 만든 견적서를 기본 프로그램(Excel)으로 연다.
fn open_with_default_app(ui: &Ui, path: &Path) {
    let file: Vec<u16> = path
        .as_os_str()
        .encode_wide()
        .chain(std::iter::once(0))
        .collect();
    let verb: Vec<u16> = OsStr::new("open")
        .encode_wide()
        .chain(std::iter::once(0))
        .collect();
    let result = unsafe {
        winapi::um::shellapi::ShellExecuteW(
            null_mut(),
            verb.as_ptr(),
            file.as_ptr(),
            null_mut(),
            null_mut(),
            winapi::um::winuser::SW_SHOWNORMAL,
        )
    };
    // ShellExecuteW 는 성공하면 32 보다 큰 값을 돌려준다 (옛 API 의 약속이다).
    if (result as usize) <= 32 {
        nwg::modal_error_message(
            &ui.window,
            TITLE,
            &format!("파일을 열지 못했습니다.\n{}", path.display()),
        );
    }
}
