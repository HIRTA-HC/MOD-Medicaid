import React, { useState, useEffect, useRef } from 'react';
import { Calendar } from 'lucide-react';

export default function CustomDateTimePicker({ placeholder, value, onChange }) {
  const [isOpen, setIsOpen] = useState(false);
  const [inputValue, setInputValue] = useState('');

  const [currentDate, setCurrentDate] = useState(new Date());
  const [selectedDay, setSelectedDay] = useState(null);

  const [hour, setHour] = useState('12');
  const [minute, setMinute] = useState('00');
  const [ampm, setAmpm] = useState('PM');

  // Reset internal state when parent clears the value (e.g. Reset button)
  useEffect(() => {
    if (value === '' || value === undefined) {
      setInputValue('');
      setSelectedDay(null);
      setHour('12');
      setMinute('00');
      setAmpm('PM');
    }
  }, [value]);

  const wrapperRef = useRef(null);

  useEffect(() => {
    function handleClickOutside(event) {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  const handleDayClick = (day) => {
    const year = currentDate.getFullYear();
    const month = currentDate.getMonth();
    const newSelected = new Date(year, month, day);
    setSelectedDay(newSelected);
    updateInputValue(newSelected, hour, minute, ampm);
  };

  const handleTimeChange = (type, val) => {
    let newHour = hour;
    let newMinute = minute;
    let newAmpm = ampm;

    if (type === 'hour') {
      newHour = val;
      setHour(val);
    } else if (type === 'minute') {
      newMinute = val;
      setMinute(val);
    } else if (type === 'ampm') {
      newAmpm = val;
      setAmpm(val);
    }

    if (selectedDay) {
      updateInputValue(selectedDay, newHour, newMinute, newAmpm);
    }
  };

  const updateInputValue = (date, h, m, ap) => {
    const mm = String(date.getMonth() + 1).padStart(2, '0');
    const dd = String(date.getDate()).padStart(2, '0');
    const yyyy = date.getFullYear();
    const newVal = `${mm}-${dd}-${yyyy}, ${h}:${m} ${ap}`;
    setInputValue(newVal);
    if (onChange) onChange(newVal);
  };

  const handlePrevMonth = () => {
    setCurrentDate(new Date(currentDate.getFullYear(), currentDate.getMonth() - 1, 1));
  };

  const handleNextMonth = () => {
    setCurrentDate(new Date(currentDate.getFullYear(), currentDate.getMonth() + 1, 1));
  };

  const year = currentDate.getFullYear();
  const month = currentDate.getMonth();
  
  const monthName = currentDate.toLocaleString('default', { month: 'long' });
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const firstDayIndex = new Date(year, month, 1).getDay();

  const days = [];
  for (let i = 0; i < firstDayIndex; i++) {
    days.push({ type: 'empty', val: i });
  }
  const today = new Date();
  for (let i = 1; i <= daysInMonth; i++) {
    const isSelected = selectedDay && 
      selectedDay.getDate() === i && 
      selectedDay.getMonth() === month && 
      selectedDay.getFullYear() === year;
    const isToday = today.getDate() === i && 
      today.getMonth() === month && 
      today.getFullYear() === year;
    days.push({ type: 'day', val: i, isSelected, isToday });
  }

  return (
    <div className="datepicker-container" ref={wrapperRef}>
      <div className="datepicker-input-wrapper">
        <input 
          type="text" 
          className="form-input-text" 
          placeholder={placeholder} 
          value={inputValue}
          readOnly
          onClick={() => setIsOpen(!isOpen)}
        />
        <button 
          type="button" 
          className="datepicker-icon-btn"
          onClick={() => setIsOpen(!isOpen)}
        >
          <Calendar size={16} />
        </button>
      </div>

      {isOpen && (
        <div className="datepicker-overlay">
          <div className="datepicker-header">
            <button type="button" className="datepicker-nav-btn" onClick={handlePrevMonth}>&lt;</button>
            <span className="datepicker-month-year">{monthName} {year}</span>
            <button type="button" className="datepicker-nav-btn" onClick={handleNextMonth}>&gt;</button>
          </div>

          <div className="datepicker-weekdays">
            <span>Su</span><span>Mo</span><span>Tu</span><span>We</span><span>Th</span><span>Fr</span><span>Sa</span>
          </div>

          <div className="datepicker-days">
            {days.map((d, index) => {
              if (d.type === 'empty') {
                return <span key={`empty-${index}`} className="datepicker-day empty"></span>;
              }
              return (
                <span 
                  key={`day-${d.val}`} 
                  className={`datepicker-day ${d.isSelected ? 'selected' : ''} ${d.isToday ? 'today' : ''}`}
                  onClick={() => handleDayClick(d.val)}
                >
                  {d.val}
                </span>
              );
            })}
          </div>

          <div className="timepicker-section">
            <span className="timepicker-label">Time</span>
            <div className="timepicker-inputs">
              <select 
                className="timepicker-select"
                value={hour}
                onChange={(e) => handleTimeChange('hour', e.target.value)}
              >
                {Array.from({ length: 12 }, (_, i) => String(i + 1).padStart(2, '0')).map(h => (
                  <option key={h} value={h}>{h}</option>
                ))}
              </select>
              <span>:</span>
              <select 
                className="timepicker-select"
                value={minute}
                onChange={(e) => handleTimeChange('minute', e.target.value)}
              >
                {['00', '15', '30', '45'].map(m => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
              <select 
                className="timepicker-select"
                value={ampm}
                onChange={(e) => handleTimeChange('ampm', e.target.value)}
              >
                <option value="AM">AM</option>
                <option value="PM">PM</option>
              </select>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
