from pathlib import Path

path = Path('dashboard/templates/dashboard/index.html')
text = path.read_text(encoding='utf-8')
old = """        // ===== BIỂU ĐỒ TRẠNG THÁI THANH TOÁN =====
        const statusCtx = document.getElementById('statusChart').getContext('2d');
        new Chart(statusCtx, {
            type: 'pie',
            data: {
                labels: statusLabels,
                datasets: [{
                    data: statusData,
                    backgroundColor: [
                        '#f59e0b',  // Cam - Chưa thanh toán
                        '#10b981',  // Xanh lá - Đã thanh toán
                    ],
                    borderColor: [
                        '#f59e0b',
                        '#10b981',
                    ],
                    borderWidth: 2,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: true,
                        position: 'bottom',
                    }
                }
            }
        });
    </script>
</body>
</html>
"""
new = """        // ===== BIỂU ĐỒ TRẠNG THÁI THANH TOÁN =====
        const statusCtx = document.getElementById('statusChart').getContext('2d');
        new Chart(statusCtx, {
            type: 'pie',
            data: {
                labels: statusLabels,
                datasets: [{
                    data: statusData,
                    backgroundColor: [
                        '#f59e0b',  // Cam - Chưa thanh toán
                        '#10b981',  // Xanh lá - Đã thanh toán
                    ],
                    borderColor: [
                        '#f59e0b',
                        '#10b981',
                    ],
                    borderWidth: 2,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: true,
                        position: 'bottom',
                    }
                }
            }
        });

        const timeLabels = JSON.parse('{{ time_labels|escapejs }}');
        const timeBookingCounts = JSON.parse('{{ time_booking_counts|escapejs }}');
        const timeRevenue = JSON.parse('{{ time_revenue|escapejs }}');
        const timePaymentPaid = JSON.parse('{{ time_payment_paid|escapejs }}');
        const timePaymentUnpaid = JSON.parse('{{ time_payment_unpaid|escapejs }}');

        const revenueCtx = document.getElementById('revenueTrendChart').getContext('2d');
        const revenueChart = new Chart(revenueCtx, {
            type: 'line',
            data: {
                labels: timeLabels.day,
                datasets: [{
                    label: 'Doanh thu',
                    data: timeRevenue.day,
                    borderColor: '#10b981',
                    backgroundColor: 'rgba(16, 185, 129, 0.2)',
                    fill: true,
                    tension: 0.3,
                    pointRadius: 4,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: true, position: 'top' }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: { callback: value => value.toLocaleString() }
                    }
                }
            }
        });

        const bookingCtx = document.getElementById('bookingTrendChart').getContext('2d');
        const bookingChart = new Chart(bookingCtx, {
            type: 'bar',
            data: {
                labels: timeLabels.day,
                datasets: [{
                    label: 'Số đơn đặt',
                    data: timeBookingCounts.day,
                    backgroundColor: '#667eea',
                    borderColor: '#4338ca',
                    borderWidth: 1,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: true, position: 'top' }
                },
                scales: {
                    y: { beginAtZero: true, ticks: { stepSize: 1 } }
                }
            }
        });

        const paymentCtx = document.getElementById('paymentTrendChart').getContext('2d');
        const paymentChart = new Chart(paymentCtx, {
            type: 'bar',
            data: {
                labels: timeLabels.day,
                datasets: [
                    {
                        label: 'Chưa Thanh Toán',
                        data: timePaymentUnpaid.day,
                        backgroundColor: '#f59e0b',
                        borderColor: '#d97706',
                        borderWidth: 1,
                    },
                    {
                        label: 'Đã Thanh Toán',
                        data: timePaymentPaid.day,
                        backgroundColor: '#10b981',
                        borderColor: '#047857',
                        borderWidth: 1,
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: true, position: 'top' }
                },
                scales: {
                    x: { stacked: true },
                    y: { stacked: true, beginAtZero: true }
                }
            }
        });

        function updateTimeframe(timeframe) {
            const labels = timeLabels[timeframe] || [];
            revenueChart.data.labels = labels;
            revenueChart.data.datasets[0].data = timeRevenue[timeframe] || [];

            bookingChart.data.labels = labels;
            bookingChart.data.datasets[0].data = timeBookingCounts[timeframe] || [];

            paymentChart.data.labels = labels;
            paymentChart.data.datasets[0].data = timePaymentUnpaid[timeframe] || [];
            paymentChart.data.datasets[1].data = timePaymentPaid[timeframe] || [];

            revenueChart.update();
            bookingChart.update();
            paymentChart.update();
        }

        document.querySelectorAll('.timeframe-button').forEach(button => {
            button.addEventListener('click', () => {
                document.querySelectorAll('.timeframe-button').forEach(btn => btn.classList.remove('active'));
                button.classList.add('active');
                updateTimeframe(button.dataset.timeframe);
            });
        });
    </script>
</body>
</html>
"""
if old not in text:
    raise ValueError('old block not found')
text = text.replace(old, new, 1)
path.write_text(text, encoding='utf-8')
print('done')
