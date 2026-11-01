package com.ieum.app;

import android.app.PendingIntent;
import android.appwidget.AppWidgetManager;
import android.appwidget.AppWidgetProvider;
import android.content.Context;
import android.content.Intent;
import android.widget.RemoteViews;

// 홈 화면 위젯: 누르면 앱이 열리자마자 듣기·말하기·보기가 바로 시작돼요
public class IeumWidget extends AppWidgetProvider {
    @Override
    public void onUpdate(Context c, AppWidgetManager m, int[] ids) {
        RemoteViews v = new RemoteViews(c.getPackageName(), R.layout.widget);
        v.setOnClickPendingIntent(R.id.w_listen, open(c, "listen", 11));
        v.setOnClickPendingIntent(R.id.w_speak, open(c, "speak", 12));
        v.setOnClickPendingIntent(R.id.w_see, open(c, "see", 13));
        m.updateAppWidget(ids, v);
    }

    private static PendingIntent open(Context c, String what, int code) {
        Intent i = new Intent(c, MainActivity.class)
            .setAction("com.ieum.app.OPEN_" + what)
            .putExtra("open", what)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_SINGLE_TOP | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        return PendingIntent.getActivity(c, code, i, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
    }
}
